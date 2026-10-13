#!/usr/bin/env bash
# ==============================================================================
# provision.sh — One-Shot Master Production Deployment for Fresh production host
# Copy the WHOLE folder (provision.sh calls its sibling scripts), then run:
#   scp -r deploy/production root@<NEW_VPS_IP>:/root/shadenet-deploy
#   ssh root@<NEW_VPS_IP> 'bash /root/shadenet-deploy/provision.sh'
# backup-host_*.sh scripts run ON backup-host, not here.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "======================================================================"
echo " Starting Full Hardened Production Provisioning on Fresh production host"
echo " Filesystem: Organized /srv/shadenet (encrypt later: 07_encrypt_at_rest.sh)"
echo " Networking: Single Caddy Ingress (80/443), Zero Public Ports"
echo " Management: WireGuard VPN (10.90.80.42) + Privacy DNS (DoT)"
echo " Containers: Caddy, Synapse, Postgres, Element, Tor, Autoheal (eggs: shadenet-core)"
echo " Resilience: Noisy Structured Logs + Automated Sentinel Repairs (3m)"
echo " Redundancy: borg append-only backups -> the backup host"
echo "======================================================================"

chmod +x "${SCRIPT_DIR}"/*.sh

echo "[Phase 0/6] Applying OS Hardening, SSH Lockdown & Security Baseline..."
"${SCRIPT_DIR}/00_hardening.sh"

echo "[Phase 1/6] Setting Up Standardized Filesystem..."
"${SCRIPT_DIR}/01_filesystem.sh"

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
echo " • Public SSH (22):       Key-only, rate-limited, fail2ban (the host console = break-glass)"
echo " • Closed to Internet:    Postgres (5432), Synapse (8008), Element, Tor"
echo " • Management VPN:        10.90.80.42 (WireGuard)"
echo "   - Operator Laptop Conf: /srv/shadenet/config/wireguard/clients/operator-laptop.conf"
echo "   - Operator Phone Conf:  /srv/shadenet/config/wireguard/clients/operator-phone.conf"
echo "   - View Phone QR Code:   shadenet-ctl vpn-qr"
echo " • Encryption at Rest:    NOT YET — verify stack, then run tang_host.sh"
echo "                         on backup-host and 07_encrypt_at_rest.sh here"
echo " • Privacy DNS Resolver:  10.90.80.42:53 (Unbound DoT to Quad9/Cloudflare)"
echo " • Automated Repairs:     Active via autoheal + shadenet-repair.timer (3 min)"
echo " • Master CLI Utility:     Run 'shadenet-ctl status' or 'shadenet-ctl logs <svc>'"
echo " • Matrix Admin Setup:     shadenet-ctl matrix-create-admin <username>"
echo " • Public Sites:          STAGED — point DNS here, then: shadenet-ctl sites-enable"
echo " • Backups:               finish with backup_host.sh, then shadenet-ctl backup-now"
echo "======================================================================"
