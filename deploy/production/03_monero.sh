#!/usr/bin/env bash
# ==============================================================================
# 03_monero.sh — Monero Full Node (Pruned) & Wallet RPC Daemon Setup
# Target: Fresh production VPS
# ==============================================================================
set -euo pipefail

MONERO_VERSION="0.18.3.4"
MONERO_TARBALL="monero-linux-x64-v${MONERO_VERSION}.tar.bz2"
MONERO_URL="https://downloads.getmonero.org/cli/${MONERO_TARBALL}"
INSTALL_DIR="/opt/monero"
DATA_DIR="/var/lib/monero"

echo "===> [1/4] Preparing directories and dependencies..."
apt-get install -y bzip2 libzmq3-dev libunbound-dev
mkdir -p "${INSTALL_DIR}" "${DATA_DIR}/data" "${DATA_DIR}/wallets"
chown -R monero:monero "${DATA_DIR}"

echo "===> [2/4] Downloading and extracting Monero CLI v${MONERO_VERSION}..."
cd /tmp
if [ ! -f "${MONERO_TARBALL}" ]; then
  wget -q "${MONERO_URL}" -O "${MONERO_TARBALL}" || {
    echo "[!] Download from getmonero.org failed; fetching from official fallback..."
    wget -q "https://github.com/monero-project/monero/releases/download/v${MONERO_VERSION}/${MONERO_TARBALL}" -O "${MONERO_TARBALL}"
  }
fi

tar -xjf "${MONERO_TARBALL}" -C "${INSTALL_DIR}" --strip-components=1
rm -f "${MONERO_TARBALL}"
chown -R root:root "${INSTALL_DIR}"
chmod +x "${INSTALL_DIR}/monerod" "${INSTALL_DIR}/monero-wallet-rpc"
ln -sf "${INSTALL_DIR}/monerod" /usr/local/bin/monerod
ln -sf "${INSTALL_DIR}/monero-wallet-rpc" /usr/local/bin/monero-wallet-rpc

echo "===> [3/4] Creating hardened systemd service for monerod..."
cat > /etc/systemd/system/monerod.service <<EOF
[Unit]
Description=Monero Full Node Daemon (Pruned)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=monero
Group=monero
WorkingDirectory=${DATA_DIR}
ExecStart=/usr/local/bin/monerod \\
  --data-dir=${DATA_DIR}/data \\
  --prune-blockchain \\
  --p2p-bind-ip=0.0.0.0 \\
  --p2p-bind-port=18080 \\
  --rpc-bind-ip=127.0.0.1 \\
  --rpc-bind-port=18081 \\
  --restricted-rpc \\
  --confirm-external-bind \\
  --no-igd \\
  --max-concurrency=4 \\
  --out-peers=32 \\
  --in-peers=16 \\
  --limit-rate-up=5120 \\
  --limit-rate-down=10240 \\
  --non-interactive

Restart=always
RestartSec=15
LimitNOFILE=65536

# System Hardening
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=${DATA_DIR}
PrivateTmp=yes
NoNewPrivileges=yes
CapabilityBoundingSet=

[Install]
WantedBy=multi-user.target
EOF

echo "===> [4/4] Creating systemd service for monero-wallet-rpc..."
# Generate random RPC password
RPC_PASS=$(openssl rand -hex 16)
mkdir -p /etc/monero
echo "RPC_USER=steward" > /etc/monero/wallet-rpc.env
echo "RPC_PASS=${RPC_PASS}" >> /etc/monero/wallet-rpc.env
chmod 600 /etc/monero/wallet-rpc.env

cat > /etc/systemd/system/monero-wallet-rpc.service <<EOF
[Unit]
Description=Monero Wallet RPC Service for Steward Agents
After=monerod.service
Requires=monerod.service

[Service]
Type=simple
User=monero
Group=monero
WorkingDirectory=${DATA_DIR}
EnvironmentFile=/etc/monero/wallet-rpc.env
ExecStart=/usr/local/bin/monero-wallet-rpc \\
  --daemon-address=127.0.0.1:18081 \\
  --rpc-bind-ip=127.0.0.1 \\
  --rpc-bind-port=18082 \\
  --rpc-login=\${RPC_USER}:\${RPC_PASS} \\
  --wallet-dir=${DATA_DIR}/wallets \\
  --disable-rpc-login=false \\
  --confirm-external-bind=false

Restart=always
RestartSec=15

ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=${DATA_DIR}
PrivateTmp=yes
NoNewPrivileges=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable monerod
systemctl start monerod
systemctl enable monero-wallet-rpc
systemctl start monero-wallet-rpc

echo "✓ Monero pruned node & wallet RPC services installed and started!"
echo "  P2P Port: 18080 (Public/Synchronizing)"
echo "  RPC Port: 18081 (Restricted, Localhost)"
echo "  Wallet RPC: 18082 (Localhost, auth in /etc/monero/wallet-rpc.env)"
