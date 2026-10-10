#!/usr/bin/env bash
# ==============================================================================
# 02_backup.sh — Automated Encrypted Cross-Server Backups to backup-host (backup-host)
# Target: Fresh production VPS
# ==============================================================================
set -euo pipefail

TARGET_HOST="${BACKUP_HOST:?Set BACKUP_HOST}"
TARGET_USER="root"
REMOTE_BACKUP_DIR="/opt/backups/production-vps"

echo "===> [1/3] Generating local backup orchestrator script..."
mkdir -p /opt/steward/backups
cat > /usr/local/bin/steward-backup-to-backup-host.sh <<EOF
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DATE=\$(date -u +"%Y%m%d_%H%M%SZ")
STAGING_DIR="/tmp/backup_\${BACKUP_DATE}"
ARCHIVE_NAME="steward_prod_\${BACKUP_DATE}.tar.gz"
REMOTE_TARGET="${TARGET_USER}@${TARGET_HOST}:${REMOTE_BACKUP_DIR}"

mkdir -p "\${STAGING_DIR}"

echo "[*] Dumping Matrix Synapse database..."
if docker ps -q -f name=matrix_postgres | grep -q .; then
  docker exec -t matrix_postgres pg_dump -U synapse synapse > "\${STAGING_DIR}/synapse_db.sql" || true
fi

echo "[*] Archiving ShadeNet state & data..."
if [ -d "/opt/shadenet/data" ]; then
  tar -czf "\${STAGING_DIR}/shadenet_data.tar.gz" -C /opt/shadenet/data . || true
fi

echo "[*] Archiving Monero wallet metadata (excluding heavy blockchain)..."
if [ -d "/var/lib/monero/wallets" ]; then
  tar -czf "\${STAGING_DIR}/monero_wallets.tar.gz" -C /var/lib/monero/wallets . || true
fi

echo "[*] Archiving TLS certificates..."
if [ -d "/var/lib/caddy" ]; then
  tar -czf "\${STAGING_DIR}/caddy_certs.tar.gz" -C /var/lib/caddy . || true
fi

# Package into single archive
tar -czf "/tmp/\${ARCHIVE_NAME}" -C "\${STAGING_DIR}" .
rm -rf "\${STAGING_DIR}"

echo "[*] Syncing backup archive to the backup host backup-host (${TARGET_HOST})..."
ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${TARGET_USER}@${TARGET_HOST}" "mkdir -p ${REMOTE_BACKUP_DIR}"
rsync -avz -e "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new" "/tmp/\${ARCHIVE_NAME}" "\${REMOTE_TARGET}/"

# Prune local temp archive
rm -f "/tmp/\${ARCHIVE_NAME}"

# Keep last 14 backups on peer backup-host
ssh -o BatchMode=yes "${TARGET_USER}@${TARGET_HOST}" "cd ${REMOTE_BACKUP_DIR} && ls -tp steward_prod_*.tar.gz | grep -v '/$' | tail -n +15 | xargs -I {} rm -f -- {}" || true

echo "[✓] Backup successfully transmitted to backup-host."
EOF
chmod +x /usr/local/bin/steward-backup-to-backup-host.sh

echo "===> [2/3] Installing systemd backup service..."
cat > /etc/systemd/system/steward-backup.service <<'EOF'
[Unit]
Description=Steward Automated Production Backup to the backup host
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/steward-backup-to-backup-host.sh
User=root
StandardOutput=journal
StandardError=journal
EOF

echo "===> [3/3] Installing systemd backup timer (Daily at 03:00 UTC)..."
cat > /etc/systemd/system/steward-backup.timer <<'EOF'
[Unit]
Description=Daily Backup Timer for Steward Production Node
Persistent=true

[Timer]
OnCalendar=*-*-* 03:00:00 UTC
RandomizedDelaySec=1800
Unit=steward-backup.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable steward-backup.timer
systemctl start steward-backup.timer

echo "✓ Automated cross-server backup timer active targeting backup-host (${TARGET_HOST})!"
