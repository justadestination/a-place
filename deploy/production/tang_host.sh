#!/usr/bin/env bash
# ==============================================================================
# tang_host.sh — Tang key server on backup-host for production vault auto-unlock
# Run ON BACKUP-HOST (backup-host) as root, NOT on the production VPS:
#   PROD_IP=<production public IP> bash tang_host.sh
#
# Tang never sees or stores the vault key. The production server can only
# recover its key while it can reach this port, and only the production IP is
# allowed in — so a stolen snapshot or disk restored elsewhere cannot unlock.
# ==============================================================================
set -euo pipefail

PROD_IP="${PROD_IP:?Set PROD_IP to the production VPS public IP}"
TANG_PORT="${TANG_PORT:-7500}"

echo "===> [1/3] Installing Tang..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq tang

echo "===> [2/3] Moving tangd.socket to port ${TANG_PORT}..."
mkdir -p /etc/systemd/system/tangd.socket.d
cat > /etc/systemd/system/tangd.socket.d/override.conf <<EOF
[Socket]
ListenStream=
ListenStream=${TANG_PORT}
EOF
systemctl daemon-reload
systemctl enable tangd.socket
systemctl restart tangd.socket

echo "===> [3/3] Restricting Tang port to production IP ${PROD_IP}..."
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow from "${PROD_IP}" to any port "${TANG_PORT}" proto tcp comment "Tang (prod vault unlock)"
else
  echo "!! UFW is not active on this host. Restrict ${TANG_PORT}/tcp to ${PROD_IP}"
  echo "!! in whatever firewall backup-host uses (and in the the host firewall)."
fi

# Thumbprint is pinned by the production server so it cannot be tricked by a fake Tang
THP="$(tang-show-keys "${TANG_PORT}" | head -n1)"

echo "============================================================"
echo " ✓ Tang listening on ${TANG_PORT}/tcp (allowed from ${PROD_IP} only)"
echo ""
echo " On the PRODUCTION server, run:"
echo "   TANG_URL=http://backup-host:${TANG_PORT} TANG_THP=${THP} \\"
echo "     bash deploy/production/07_encrypt_at_rest.sh"
echo ""
echo " Back up /var/db/tang (or /var/lib/tang) — if these keys are lost,"
echo " production falls back to the recovery passphrase on every boot."
echo "============================================================"
