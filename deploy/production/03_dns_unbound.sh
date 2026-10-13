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
# - Bound strictly to 127.0.0.1 and WireGuard VPN (10.90.80.42). ZERO public exposure.
# ==============================================================================
set -euo pipefail

ROOT_DIR="/srv/shadenet"
UNBOUND_CONF_DIR="${ROOT_DIR}/config/unbound"
SERVER_VPN_IP="10.90.80.42"

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
    # Start even if wg0 is not up yet (boot ordering); bind once it appears
    ip-freebind: yes

    # Protocol settings
    do-ip4: yes
    do-ip6: no
    do-udp: yes
    do-tcp: yes

    # Access control (Localhost + WireGuard Subnet ONLY)
    access-control: 127.0.0.0/8 allow
    access-control: 10.90.80.0/24 allow
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

    # Security & DNSSEC (trust anchor file is provided by the distro package)
    val-permissive-mode: no

    # Without a CA bundle every DoT handshake fails and ALL queries SERVFAIL
    tls-cert-bundle: /etc/ssl/certs/ca-certificates.crt

    # Local Private Zone for Internal Infrastructure Discovery
    private-domain: "internal"
    local-zone: "internal." static
    local-data: "matrix.internal. IN A ${SERVER_VPN_IP}"
    local-data: "shadenet.internal. IN A ${SERVER_VPN_IP}"
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

# Test the FULL config (distro defaults + ours), not just our fragment
unbound-checkconf

echo "===> [3/3] Starting and enabling Unbound service..."
systemctl restart unbound
systemctl enable unbound

# Resolution must work AND DNSSEC must reject a deliberately broken domain.
# (Checking SERVFAIL alone passes when Unbound is failing everything.)
sleep 2
if [ -z "$(dig @127.0.0.1 +time=5 +tries=3 +short A example.com)" ]; then
  echo "!! Unbound cannot resolve example.com — check: journalctl -u unbound" >&2
  exit 1
fi
if [ "$(dig @127.0.0.1 +time=5 +tries=2 dnssec-failed.org | awk '/status:/{print $6}' | tr -d ,)" != "SERVFAIL" ]; then
  echo "!! DNSSEC validation is NOT working (dnssec-failed.org resolved)." >&2
  exit 1
fi

# Only switch the host resolver once Unbound is proven good
cp -L /etc/resolv.conf /etc/resolv.conf.bak 2>/dev/null || true

# A REGULAR file, not a symlink: Ubuntu 26.04 AppArmor profiles (dig, etc.)
# may only read /etc/resolv.conf itself. systemd-resolved leaves a regular
# file alone ("foreign" mode), and nsswitch uses it directly.
rm -f /etc/resolv.conf /etc/resolv.conf.shadenet
printf 'nameserver 127.0.0.1\noptions edns0 trust-ad\n' > /etc/resolv.conf
chmod 644 /etc/resolv.conf
getent hosts example.com >/dev/null || { echo "!! Host resolution via Unbound failed" >&2; exit 1; }


echo "✓ Privacy Unbound DNS active on 127.0.0.1:53 and ${SERVER_VPN_IP}:53"
