#!/usr/bin/env bash
# ==============================================================================
# 05_tor.sh — Hardened Tor Daemon & Onion Services Configuration
# Target: Fresh production VPS
#
# IMPORTANT PRIMARY TOS NOTICE:
# - Exit relays are STRICTLY FORBIDDEN on the host and will lead to termination.
# - ExitRelay is explicitly set to 0.
# - This script configures Tor as:
#   1. Local SOCKS5 Proxy (127.0.0.1:9050) for Monero transaction anonymization
#   2. Onion Services (v3 Hidden Services) for ShadeNet, Matrix, and Monero RPC
#   3. Emergency Out-of-Band SSH access over Tor
# ==============================================================================
set -euo pipefail

echo "===> [1/4] Installing Tor and dependencies..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq tor tor-geoipdb

echo "===> [2/4] Configuring /etc/tor/torrc with zero exit relay..."
cat > /etc/tor/torrc <<'EOF'
## ====================================================================
## ShadeNet Hardened Tor Configuration
## ====================================================================

## Run as client and local SOCKS5 proxy
SOCKSPort 127.0.0.1:9050
SocksPolicy accept 127.0.0.1
SocksPolicy reject *

## ABSOLUTELY NO RELAY / NO EXIT (Complies with the host AUP)
ORPort 0
ExitRelay 0
ExitPolicy reject *:*

## Data Directory
DataDirectory /var/lib/tor

## Onion Service 1: ShadeNet Web & Zine Engine
HiddenServiceDir /var/lib/tor/shadenet_service/
HiddenServiceVersion 3
HiddenServicePort 80 127.0.0.1:8765

## Onion Service 2: Matrix Synapse Homeserver
HiddenServiceDir /var/lib/tor/matrix_service/
HiddenServiceVersion 3
HiddenServicePort 80 127.0.0.1:8008

## Onion Service 3: Monero Node Restricted RPC
HiddenServiceDir /var/lib/tor/monero_service/
HiddenServiceVersion 3
HiddenServicePort 18081 127.0.0.1:18081

## Onion Service 4: Emergency Management SSH (Out-of-band access)
HiddenServiceDir /var/lib/tor/ssh_service/
HiddenServiceVersion 3
HiddenServicePort 22 127.0.0.1:22
EOF

echo "===> [3/4] Securing Tor permissions and restarting daemon..."
chown -R debian-tor:debian-tor /var/lib/tor /etc/tor
chmod 700 /var/lib/tor
systemctl daemon-reload
systemctl enable tor
systemctl restart tor

# Wait up to 15 seconds for keys and hostnames to generate
echo "Waiting for Onion Service v3 keys to initialize..."
for i in {1..15}; do
  if [ -f /var/lib/tor/shadenet_service/hostname ]; then
    break
  fi
  sleep 1
done

echo "===> [4/4] Extracting Onion addresses..."
mkdir -p /etc/shadenet
ADDR_FILE="/etc/shadenet/onion_addresses.txt"

{
  echo "============================================================"
  echo " SHADENET PRODUCTION ONION SERVICES (v3)"
  echo " Generated: $(date -u)"
  echo "============================================================"
  if [ -f /var/lib/tor/shadenet_service/hostname ]; then
    echo "ShadeNet Web / Zine:  http://$(cat /var/lib/tor/shadenet_service/hostname)"
  fi
  if [ -f /var/lib/tor/matrix_service/hostname ]; then
    echo "Matrix Synapse (.onion): http://$(cat /var/lib/tor/matrix_service/hostname)"
  fi
  if [ -f /var/lib/tor/monero_service/hostname ]; then
    echo "Monero Restricted RPC:   http://$(cat /var/lib/tor/monero_service/hostname):18081"
  fi
  if [ -f /var/lib/tor/ssh_service/hostname ]; then
    echo "Tor Emergency SSH:       $(cat /var/lib/tor/ssh_service/hostname):22"
  fi
  echo "============================================================"
} > "${ADDR_FILE}"

cat "${ADDR_FILE}"

# Update monerod service to route transaction broadcasts through Tor if present
if [ -f /etc/systemd/system/monerod.service ]; then
  if ! grep -q "tx-proxy tor" /etc/systemd/system/monerod.service; then
    echo "Enabling Monero transaction broadcast via Tor SOCKS5 proxy..."
    sed -i '/--prune-blockchain/a \  --tx-proxy tor,127.0.0.1:9050 \\' /etc/systemd/system/monerod.service
    systemctl daemon-reload
    systemctl restart monerod.service || true
  fi
fi

echo "✓ Tor Daemon & Onion Services successfully deployed!"
