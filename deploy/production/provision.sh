#!/usr/bin/env bash
# ==============================================================================
# provision.sh — One-Shot Master Production Deployment for Fresh production host
# Run on fresh server as root:
#   bash deploy/production/provision.sh
# Or remotely from operator workstation:
#   ssh root@<NEW_VPS_IP> 'bash -s' < deploy/production/provision.sh
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "======================================================================"
echo " Starting Full Hardened Production Provisioning on Fresh production host"
echo " Filesystem: Organized /srv/shadenet + LUKS2 Encryption at Rest"
echo " Networking: Single Caddy Ingress (80/443), Zero Public Ports"
echo " Management: WireGuard VPN (203.0.113.1) + Privacy DNS (DoT)"
echo " Containers: Caddy, Synapse, Postgres, Monerod, Element, Tor, Autoheal"
echo " Resilience: Noisy Structured Logs + Automated Sentinel Repairs (3m)"
echo " Redundancy: Encrypted Cross-Server Backups -> the backup host"
echo "======================================================================"

chmod +x "${SCRIPT_DIR}"/*.sh

echo "[Phase 1/6] Setting Up Standardized Filesystem & LUKS2 Encryption at Rest..."
"${SCRIPT_DIR}/01_filesystem_luks.sh"

echo "[Phase 2/6] Configuring WireGuard VPN Mesh & Zero-Exposed-Port Firewall..."
"${SCRIPT_DIR}/02_wireguard_vpn.sh"

echo "[Phase 3/6] Deploying Privacy DNS Server (Unbound with DNS-over-TLS)..."
"${SCRIPT_DIR}/03_dns_unbound.sh"

echo "[Phase 4/6] Deploying Isolated Container Stack & Single Caddy Ingress..."
"${SCRIPT_DIR}/04_containers_compose.sh"

echo "[Phase 5/6] Initializing Noisy Logging, Automated Repairs & shadenet-ctl..."
"${SCRIPT_DIR}/05_logging_repairs.sh"

echo "[Phase 6/6] Establishing Automated Encrypted Backups to backup-host..."
"${SCRIPT_DIR}/06_backup_sync.sh"

echo ""
echo "Starting container stack..."
cd /srv/shadenet && docker compose up -d

echo "======================================================================"
echo " ✓ Institutional Production Stack Successfully Deployed!"
echo "======================================================================"
echo " • Single Ingress Ports:  80/tcp, 443/tcp (Caddy), 51820/udp (WireGuard)"
echo " • Closed to Internet:    SSH (22), Postgres (5432), Synapse (8008), Monero RPC"
echo " • Management VPN:        203.0.113.1 (WireGuard)"
echo "   - Operator Laptop Conf: /srv/shadenet/config/wireguard/clients/operator-laptop.conf"
echo "   - Operator Phone Conf:  /srv/shadenet/config/wireguard/clients/operator-phone.conf"
echo "   - View Phone QR Code:   shadenet-ctl vpn-qr"
echo " • Encryption at Rest:    LUKS2 AES-XTS on /srv/shadenet/data"
echo " • Privacy DNS Resolver:  203.0.113.1:53 (Unbound DoT to Quad9/Cloudflare)"
echo " • Automated Repairs:     Active via autoheal + shadenet-repair.timer (3 min)"
echo " • Master CLI Utility:     Run 'shadenet-ctl status' or 'shadenet-ctl logs <svc>'"
echo " • Matrix Admin Setup:     shadenet-ctl matrix-create-admin <username> <password>"
echo "======================================================================"
