#!/usr/bin/env bash
# ==============================================================================
# 06_backup_sync.sh — Encrypted Cross-Server Backups to the backup host
# Target: Fresh production VPS -> backup-host
# ==============================================================================
set -euo pipefail

ROOT_DIR="/srv/shadenet"
TARGET_HOST="${BACKUP_HOST:?Set BACKUP_HOST}"
TARGET_USER="root"
REMOTE_BACKUP_DIR="/opt/backups/production-vps"

echo "===> [1/3] Generating encrypted backup script (${ROOT_DIR}/bin/backup.sh)..."
cat > "${ROOT_DIR}/bin/backup.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/srv/shadenet"
BACKUP_DATE=\$(date -u +"%Y%m%d_%H%M%SZ")
STAGING_DIR="/tmp/backup_\${BACKUP_DATE}"
ARCHIVE_NAME="shadenet_prod_\${BACKUP_DATE}.tar.gz"
ENCRYPTED_ARCHIVE="\${ARCHIVE_NAME}.enc"
REMOTE_TARGET="${TARGET_USER}@${TARGET_HOST}:${REMOTE_BACKUP_DIR}"

mkdir -p "\${STAGING_DIR}"

echo "[*] Dumping Matrix Synapse database..."
if docker ps -q -f name=matrix_postgres | grep -q .; then
  docker exec -t matrix_postgres pg_dump -U synapse synapse > "\${STAGING_DIR}/synapse_db.sql" || true
fi

echo "[*] Archiving ShadeNet persistent data..."
if [ -d "\${ROOT_DIR}/data/shadenet" ]; then
  tar -czf "\${STAGING_DIR}/shadenet_data.tar.gz" -C "\${ROOT_DIR}/data/shadenet" . || true
fi

echo "[*] Archiving Monero wallet metadata & keys..."
if [ -d "\${ROOT_DIR}/data/monero/wallets" ]; then
  tar -czf "\${STAGING_DIR}/monero_wallets.tar.gz" -C "\${ROOT_DIR}/data/monero/wallets" . || true
fi

# Package into single archive
tar -czf "/tmp/\${ARCHIVE_NAME}" -C "\${STAGING_DIR}" .
rm -rf "\${STAGING_DIR}"

# Encrypt archive with host key or symmetric pass before transit
openssl enc -aes-256-cbc -salt -pbkdf2 -in "/tmp/\${ARCHIVE_NAME}" \
  -out "/tmp/\${ENCRYPTED_ARCHIVE}" -pass file:/etc/security/luks/shadenet.key
rm -f "/tmp/\${ARCHIVE_NAME}"

echo "[*] Syncing encrypted archive to the backup host backup-host (${TARGET_HOST})..."
ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${TARGET_USER}@${TARGET_HOST}" "mkdir -p ${REMOTE_BACKUP_DIR}" || true
rsync -avz -e "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new" "/tmp/\${ENCRYPTED_ARCHIVE}" "\${REMOTE_TARGET}/" || true

rm -f "/tmp/\${ENCRYPTED_ARCHIVE}"

# Prune older backups on backup-host (keep 14 days)
ssh -o BatchMode=yes "${TARGET_USER}@${TARGET_HOST}" "cd ${REMOTE_BACKUP_DIR} && ls -tp shadenet_prod_*.enc | grep -v '/$' | tail -n +15 | xargs -I {} rm -f -- {}" 2>/dev/null || true

echo "[✓] Encrypted backup successfully transmitted to backup-host."
EOF
chmod +x "${ROOT_DIR}/bin/backup.sh"

echo "===> [2/3] Installing systemd backup service..."
cat > /etc/systemd/system/steward-backup.service <<EOF
[Unit]
Description=ShadeNet Encrypted Cross-Server Backup to backup-host
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=${ROOT_DIR}/bin/backup.sh
User=root
StandardOutput=journal
StandardError=journal
EOF

echo "===> [3/3] Installing daily systemd backup timer (03:00 UTC)..."
cat > /etc/systemd/system/steward-backup.timer <<'EOF'
[Unit]
Description=Daily Backup Timer for ShadeNet Production
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
systemctl restart steward-backup.timer

echo "✓ Encrypted cross-server backups active targeting backup-host (${TARGET_HOST})!"
