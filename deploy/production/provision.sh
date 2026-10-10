#!/usr/bin/env bash
# ==============================================================================
# provision.sh — One-Shot Master Production Deployment for Fresh production host
# Run on fresh server as root:
#   bash provision.sh
# Or remotely from operator laptop:
#   ssh root@<NEW_VPS_IP> 'bash -s' < deploy/production/provision.sh
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "======================================================================"
echo " Starting Full Production Provisioning on Fresh production host"
echo " Node: Monero Pruned Node + Matrix Synapse + Element Web + Tor + ShadeNet"
echo " Security: UFW + SSH Hardening + Fail2ban + Backups to backup-host"
echo "======================================================================"

chmod +x "${SCRIPT_DIR}/01_hardening.sh"
chmod +x "${SCRIPT_DIR}/02_backup.sh"
chmod +x "${SCRIPT_DIR}/03_monero.sh"
chmod +x "${SCRIPT_DIR}/04_matrix_element.sh"
chmod +x "${SCRIPT_DIR}/05_tor.sh"

echo "[Phase 1/6] Running OS Hardening & Security Baseline..."
"${SCRIPT_DIR}/01_hardening.sh"

echo "[Phase 2/6] Setting Up Automated Backups to backup-host (backup-host)..."
"${SCRIPT_DIR}/02_backup.sh"

echo "[Phase 3/6] Deploying Monero Full Node (Pruned) & Wallet RPC..."
"${SCRIPT_DIR}/03_monero.sh"

echo "[Phase 4/6] Deploying Matrix Synapse + Element Web + Caddy..."
"${SCRIPT_DIR}/04_matrix_element.sh"

echo "[Phase 5/6] Deploying Hardened Tor Daemon & Onion Services..."
"${SCRIPT_DIR}/05_tor.sh"

echo "[Phase 6/6] Deploying ShadeNet NightCal Core Service..."
mkdir -p /opt/shadenet
if [ -d "/opt/shadenet/shadenet" ]; then
  chown -R www-data:www-data /opt/shadenet
fi

cat > /etc/systemd/system/shadenet.service <<'EOF'
[Unit]
Description=Shadenet NightCal & Steward Web Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/shadenet
Environment="PYTHONPATH=/opt/shadenet"
Environment="NIGHTCAL_PORT=8765"
Environment="NIGHTCAL_HOST=127.0.0.1"
ExecStart=/usr/bin/python3 -m shadenet.nightcal.server
Restart=always
RestartSec=5

ProtectSystem=full
PrivateTmp=yes
NoNewPrivileges=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable shadenet.service
systemctl restart shadenet.service || true

echo "======================================================================"
echo " ✓ Turnkey Production Deployment Complete!"
echo "   - Monerod P2P: 0.0.0.0:18080 (Synchronizing pruned blockchain)"
echo "   - Monero Wallet RPC: 127.0.0.1:18082"
echo "   - Monero Tx Anonymization: Via Tor SOCKS5 (127.0.0.1:9050)"
echo "   - Matrix Synapse: https://matrix.example.org"
echo "   - Element Web: https://chat.example.org"
echo "   - ShadeNet Core: https://shady.example.org"
echo "   - Tor Onion Addresses: /etc/shadenet/onion_addresses.txt"
echo "   - Backup Timer: Daily @ 03:00 UTC -> backup-host"
echo "======================================================================"
