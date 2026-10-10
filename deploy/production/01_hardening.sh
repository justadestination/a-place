#!/usr/bin/env bash
# ==============================================================================
# 01_hardening.sh — OS Hardening, Users, Firewall & Security Baseline
# Target: Fresh the host Cloud Ubuntu 24.04 / Debian 12 VPS
# ==============================================================================
set -euo pipefail

echo "===> [1/5] Updating packages and installing essential tools..."
export DEBIAN_FRONTEND=noninteractive
apt-get update && apt-get upgrade -y
apt-get install -y \
  ufw \
  fail2ban \
  curl \
  wget \
  jq \
  git \
  rsync \
  tar \
  ca-certificates \
  gnupg \
  lsb-release \
  python3 \
  python3-pip \
  python3-venv \
  python3-cryptography \
  python3-cbor2 \
  build-essential \
  htop \
  unattended-upgrades

# Enable automatic security updates
dpkg-reconfigure -f noninteractive -p low unattended-upgrades

echo "===> [2/5] Creating dedicated unprivileged system users..."
# 'steward' runs ShadeNet / NightCal / Agent services
if ! id "steward" &>/dev/null; then
  useradd -r -m -s /bin/bash steward
  usermod -aG www-data steward 2>/dev/null || true
fi

# 'monero' runs monerod daemon in isolation
if ! id "monero" &>/dev/null; then
  useradd -r -m -d /var/lib/monero -s /usr/sbin/nologin monero
fi

echo "===> [3/5] Applying kernel and sysctl network hardening..."
cat > /etc/sysctl.d/99-hardened.conf <<'EOF'
# IP Spoofing & ICMP protection
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0

# TCP SYN Flood Protection
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_max_syn_backlog = 4096
net.ipv4.tcp_synack_retries = 2

# Log Martians & ignore broadcast pings
net.ipv4.conf.all.log_martians = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1

# Max memory map count for Monero & DB performance
vm.max_map_count = 262144
fs.file-max = 2097152
EOF
sysctl --system >/dev/null

echo "===> [4/5] Hardening SSH daemon configuration..."
cat > /etc/ssh/sshd_config.d/99-hardened.conf <<'EOF'
PermitRootLogin prohibit-password
PasswordAuthentication no
ChallengeResponseAuthentication no
KbdInteractiveAuthentication no
UsePAM yes
X11Forwarding no
MaxAuthTries 4
ClientAliveInterval 300
ClientAliveCountMax 2
EOF
systemctl reload ssh || systemctl reload sshd || true

echo "===> [5/5] Configuring UFW firewall rules..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing

# Public Services
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP Caddy ACME'
ufw allow 443/tcp comment 'HTTPS Caddy'
ufw allow 8448/tcp comment 'Matrix Federation'
ufw allow 18080/tcp comment 'Monero P2P Network'

# Enable firewall
ufw --force enable
ufw status verbose

# Fail2ban configuration
cat > /etc/fail2ban/jail.local <<'EOF'
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true
port = 22
mode = aggressive
EOF
systemctl restart fail2ban
systemctl enable fail2ban

echo "✓ Baseline OS hardening, users, firewall, and fail2ban active!"
