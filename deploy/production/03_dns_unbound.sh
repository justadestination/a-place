#!/usr/bin/env bash
# ==============================================================================
# 03_dns_unbound.sh — Privacy Recursive DNS Server (Unbound with DNS-over-TLS)
# Target: Fresh production VPS (Debian 12 / Ubuntu 24.04)
#
# FEATURES:
# - Strict DNS-over-TLS (DoT) to Quad9 (9.9.9.9) and Cloudflare (1.1.1.1)
# - DNSSEC validation & QNAME minimization
# - Zero query logging (privacy-preserving)
# - Local authoritative zone for `.internal` service discovery
# - Bound strictly to 127.0.0.1 and WireGuard VPN (203.0.113.1). ZERO public exposure.
# ==============================================================================
set -euo pipefail

ROOT_DIR="/srv/shadenet"
UNBOUND_CONF_DIR="${ROOT_DIR}/config/unbound"
SERVER_VPN_IP="203.0.113.1"

echo "===> [1/3] Installing Unbound and DNSSEC trust anchor..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq unbound unbound-anchor ca-certificates dnsutils

mkdir -p "${UNBOUND_CONF_DIR}" /etc/unbound/unbound.conf.d

echo "===> [2/3] Writing hardened privacy Unbound configuration..."
cat > /etc/unbound/unbound.conf.d/shadenet.conf <<EOF
server:
    # Interface binding (Local loopback + WireGuard VPN ONLY)
    interface: 127.0.0.1
    interface: ${SERVER_VPN_IP}
    port: 53

    # Protocol settings
    do-ip4: yes
    do-ip6: no
    do-udp: yes
    do-tcp: yes

    # Access control (Localhost + WireGuard Subnet ONLY)
    access-control: 127.0.0.0/8 allow
    access-control: 203.0.113.0/24 allow
    access-control: 0.0.0.0/0 refuse

    # Privacy & Anonymity Settings
    hide-identity: yes
    hide-version: yes
    qname-minimisation: yes
    use-caps-for-id: yes
    val-clean-additional: yes

    # Zero Logging (Anti-Surveillance)
    use-syslog: yes
    log-queries: no
    log-replies: no
    verbosity: 1

    # Caching & Performance
    cache-min-ttl: 300
    cache-max-ttl: 86400
    msg-cache-size: 16m
    rrset-cache-size: 32m
    infra-cache-numhosts: 10000
    so-reuseport: yes

    # Security & DNSSEC
    auto-trust-anchor-file: "/var/lib/unbound/root.key"
    val-permissive-mode: no

    # Local Private Zone for Internal Infrastructure Discovery
    private-domain: "internal"
    local-zone: "internal." static
    local-data: "matrix.internal. IN A ${SERVER_VPN_IP}"
    local-data: "shadenet.internal. IN A ${SERVER_VPN_IP}"
    local-data: "monero.internal. IN A ${SERVER_VPN_IP}"
    local-data: "vault.internal. IN A ${SERVER_VPN_IP}"

# Forward all external queries via DNS-over-TLS (Port 853)
forward-zone:
    name: "."
    forward-tls-upstream: yes
    # Quad9 Primary (Strict Privacy & Malware Filtering)
    forward-addr: 9.9.9.9@853#dns.quad9.net
    forward-addr: 149.112.112.112@853#dns.quad9.net
    # Cloudflare Secondary
    forward-addr: 1.1.1.1@853#cloudflare-dns.com
    forward-addr: 1.0.0.1@853#cloudflare-dns.com
EOF

# Update root trust anchor
unbound-anchor -a /var/lib/unbound/root.key || true

# Test configuration syntax
unbound-checkconf /etc/unbound/unbound.conf.d/shadenet.conf

echo "===> [3/3] Starting and enabling Unbound service..."
systemctl restart unbound
systemctl enable unbound

# Set host resolver to use local Unbound
if [ -f /etc/resolv.conf ]; then
  # Preserve backup
  cp /etc/resolv.conf /etc/resolv.conf.bak || true
fi

echo "nameserver 127.0.0.1" > /etc/resolv.conf.shadenet
ln -sf /etc/resolv.conf.shadenet /etc/resolv.conf || true

echo "✓ Privacy Unbound DNS active on 127.0.0.1:53 and ${SERVER_VPN_IP}:53"
