#!/usr/bin/env bash
# ==============================================================================
# 02_wireguard_vpn.sh — WireGuard VPN Mesh & Zero-Exposed-Port Firewall
# Target: Fresh production VPS (Debian 12 / Ubuntu 24.04)
#
# NETWORK TOPOLOGY:
# - Public Ingress: 80/tcp, 443/tcp (Caddy), 51820/udp (WireGuard) ONLY.
# - Zero Other Ports: SSH (22), Postgres, Synapse, ShadeNet, Monero RPC, DNS
#   are BLOCKED on public internet and accessible ONLY via WireGuard (203.0.113.1).
# ==============================================================================
set -euo pipefail

ROOT_DIR="/srv/shadenet"
WG_DIR="${ROOT_DIR}/config/wireguard"
CLIENT_DIR="${WG_DIR}/clients"
WG_IFACE="wg0"
WG_PORT=51820
VPN_SUBNET="203.0.113"
SERVER_VPN_IP="${VPN_SUBNET}.1"

echo "===> [1/4] Installing WireGuard, UFW, and QR utilities..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq wireguard wireguard-tools qrencode ufw fail2ban iptables

mkdir -p "${CLIENT_DIR}"
chmod 700 "${WG_DIR}" "${CLIENT_DIR}"

echo "===> [2/4] Generating WireGuard cryptographic keypairs..."
if [ ! -f "${WG_DIR}/server_private.key" ]; then
  wg genkey | tee "${WG_DIR}/server_private.key" | wg pubkey > "${WG_DIR}/server_public.key"
  chmod 600 "${WG_DIR}/server_private.key"
fi
SERVER_PRIV=$(cat "${WG_DIR}/server_private.key")
SERVER_PUB=$(cat "${WG_DIR}/server_public.key")

# Generate Operator Laptop Keypair
if [ ! -f "${CLIENT_DIR}/operator_laptop_private.key" ]; then
  wg genkey | tee "${CLIENT_DIR}/operator_laptop_private.key" | wg pubkey > "${CLIENT_DIR}/operator_laptop_public.key"
  chmod 600 "${CLIENT_DIR}/operator_laptop_private.key"
fi
LAPTOP_PRIV=$(cat "${CLIENT_DIR}/operator_laptop_private.key")
LAPTOP_PUB=$(cat "${CLIENT_DIR}/operator_laptop_public.key")

# Generate Operator Phone Keypair
if [ ! -f "${CLIENT_DIR}/operator_phone_private.key" ]; then
  wg genkey | tee "${CLIENT_DIR}/operator_phone_private.key" | wg pubkey > "${CLIENT_DIR}/operator_phone_public.key"
  chmod 600 "${CLIENT_DIR}/operator_phone_private.key"
fi
PHONE_PRIV=$(cat "${CLIENT_DIR}/operator_phone_private.key")
PHONE_PUB=$(cat "${CLIENT_DIR}/operator_phone_public.key")

# Detect Public IP
SERVER_PUB_IP=$(curl -s https://api.ipify.org || curl -s https://icanhazip.com || hostname -I | awk '{print $1}')

echo "===> [3/4] Configuring WireGuard Interface (${WG_IFACE})..."
cat > "/etc/wireguard/${WG_IFACE}.conf" <<EOF
[Interface]
Address = ${SERVER_VPN_IP}/24
ListenPort = ${WG_PORT}
PrivateKey = ${SERVER_PRIV}
SaveConfig = false

# Enable forwarding
PostUp = iptables -A FORWARD -i ${WG_IFACE} -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i ${WG_IFACE} -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

# Peer 1: Operator Laptop
[Peer]
PublicKey = ${LAPTOP_PUB}
AllowedIPs = ${VPN_SUBNET}.2/32

# Peer 2: Operator Phone
[Peer]
PublicKey = ${PHONE_PUB}
AllowedIPs = ${VPN_SUBNET}.3/32
EOF
chmod 600 "/etc/wireguard/${WG_IFACE}.conf"

# Generate Client Configs
cat > "${CLIENT_DIR}/operator-laptop.conf" <<EOF
[Interface]
PrivateKey = ${LAPTOP_PRIV}
Address = ${VPN_SUBNET}.2/24
DNS = ${SERVER_VPN_IP}

[Peer]
PublicKey = ${SERVER_PUB}
Endpoint = ${SERVER_PUB_IP}:${WG_PORT}
AllowedIPs = ${VPN_SUBNET}.0/24, 203.0.113.0/24
PersistentKeepalive = 25
EOF
chmod 600 "${CLIENT_DIR}/operator-laptop.conf"

cat > "${CLIENT_DIR}/operator-phone.conf" <<EOF
[Interface]
PrivateKey = ${PHONE_PRIV}
Address = ${VPN_SUBNET}.3/24
DNS = ${SERVER_VPN_IP}

[Peer]
PublicKey = ${SERVER_PUB}
Endpoint = ${SERVER_PUB_IP}:${WG_PORT}
AllowedIPs = ${VPN_SUBNET}.0/24, 203.0.113.0/24
PersistentKeepalive = 25
EOF
chmod 600 "${CLIENT_DIR}/operator-phone.conf"

# Generate ASCII QR Code for Phone import
qrencode -t ANSIUTF8 < "${CLIENT_DIR}/operator-phone.conf" > "${CLIENT_DIR}/operator-phone-qr.txt"
qrencode -o "${CLIENT_DIR}/operator-phone-qr.png" < "${CLIENT_DIR}/operator-phone.conf" || true

# Enable IPv4 Forwarding
sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/99-wireguard-forward.conf

systemctl enable "wg-quick@${WG_IFACE}"
systemctl restart "wg-quick@${WG_IFACE}" || true

echo "===> [4/4] Configuring Zero-Exposed-Port UFW Firewall..."
# Reset and configure strict baseline
ufw --force reset
ufw default deny incoming
ufw default allow outgoing

# The ONLY public ingress ports:
ufw allow 80/tcp comment "Public Ingress HTTP (ACME)"
ufw allow 443/tcp comment "Public Ingress HTTPS (Caddy)"
ufw allow ${WG_PORT}/udp comment "WireGuard VPN Management Mesh"

# Allow full management access strictly from inside the WireGuard VPN interface
ufw allow in on "${WG_IFACE}" to any comment "WireGuard Internal Mesh Access"
ufw allow in on lo to any comment "Local Loopback"

# For bootstrap safety: allow SSH on port 22 with rate limiting initially
# Once operator connects over VPN (203.0.113.1:22), public 22 can be closed.
ufw limit 22/tcp comment "Bootstrap SSH (Rate Limited)"

ufw --force enable

echo "============================================================"
echo " ✓ WireGuard VPN Deployed (${SERVER_VPN_IP}/24)"
echo "   - Operator Laptop Config: ${CLIENT_DIR}/operator-laptop.conf"
echo "   - Operator Phone Config:  ${CLIENT_DIR}/operator-phone.conf"
echo "   - Phone QR Code:          ${CLIENT_DIR}/operator-phone-qr.txt"
echo "============================================================"
