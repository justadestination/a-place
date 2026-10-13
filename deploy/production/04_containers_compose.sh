#!/usr/bin/env bash
# ==============================================================================
# 04_containers_compose.sh — The Nest: Isolated Container Stack & Single Ingress
# Target: the host Production VPS (Ubuntu 24.04+)
#
# ARCHITECTURE:
# - Single Ingress: Caddy is the ONLY container with public ports (80/443).
# - Zero Exposed Ports: Postgres, Synapse, Element, Tor have NO host port bindings.
# - Storage: All persistent volumes under /srv/shadenet/data (encrypted later
#   by 07_encrypt_at_rest.sh).
# - Networks: edge (fixed subnet, egress allowed), matrix-net (internal only).
# - Public hostnames are STAGED but DISABLED until DNS cutover:
#     shadenet-ctl sites-enable    (after pointing DNS at this server)
# - Eggs (not built here): shadenet-core — see the commented block in compose.yaml.
# ==============================================================================
set -euo pipefail

ROOT_DIR="/srv/shadenet"
CONFIG_DIR="${ROOT_DIR}/config"
DATA_DIR="${ROOT_DIR}/data"
COMPOSE_FILE="${ROOT_DIR}/compose.yaml"
ENV_FILE="${ROOT_DIR}/.env"
SERVER_VPN_IP="10.90.80.42"

# Matrix identity — server_name is PERMANENT once users exist
MATRIX_SERVER_NAME="shadesr.net"
MATRIX_HOST="matrix.shadesr.net"
CHAT_HOST="chat.shadesr.net"

# Fixed edge subnet so Tor can target Caddy by IP (HiddenServicePort needs an IP)
EDGE_SUBNET="172.30.0.0/24"
CADDY_EDGE_IP="172.30.0.10"

# Pinned image versions (bump deliberately, never :latest)
CADDY_IMAGE="caddy:2.11.7-alpine"
SYNAPSE_IMAGE="matrixdotorg/synapse:v1.162.0"
POSTGRES_IMAGE="postgres:16.15-alpine"
ELEMENT_IMAGE="vectorim/element-web:v1.12.30"
ALPINE_IMAGE="alpine:3.24"
AUTOHEAL_IMAGE="willfarrell/autoheal:1.2.0"

SYNAPSE_UID=991

echo "===> [1/8] Installing Docker Engine and Compose from the distro archive..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq docker.io docker-compose-v2

mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "50m", "max-file": "5" },
  "no-new-privileges": true,
  "live-restore": true
}
EOF
systemctl enable docker
systemctl restart docker

echo "===> [2/8] Generating cryptographically secure secrets in ${ENV_FILE}..."
if [ ! -f "${ENV_FILE}" ]; then
  ( umask 077
    cat > "${ENV_FILE}" <<EOF
# ShadeNet Production Environment Secrets
POSTGRES_PASSWORD=$(openssl rand -hex 24)
SYNAPSE_REGISTRATION_SECRET=$(openssl rand -hex 32)
SYNAPSE_MACAROON_SECRET=$(openssl rand -hex 32)
SYNAPSE_FORM_SECRET=$(openssl rand -hex 32)
SHADENET_SECRET_KEY=$(openssl rand -hex 32)
NIGHTCAL_BEARER=$(openssl rand -hex 24)
EOF
  )
fi
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

echo "===> [3/8] Writing Caddy config (single ingress, public sites staged)..."
mkdir -p "${CONFIG_DIR}/caddy/sites-available" "${CONFIG_DIR}/caddy/sites-enabled"
cat > "${CONFIG_DIR}/caddy/Caddyfile" <<EOF
{
    email ops@example.org
    admin off
    log {
        output file /var/log/caddy/access.log {
            roll_size 50mb
            roll_keep 5
        }
        format json
    }
}

# Onion ingress — reachable only from the Tor container on the edge network
:8080 {
    respond "ShadeNet onion — nest ready, eggs pending" 200
}

# WireGuard management ingress
http://${SERVER_VPN_IP} {
    respond "ShadeNet Management Ingress (WireGuard Secured)" 200
}

# Public sites live in sites-available/ and are symlinked in at DNS cutover
import /etc/caddy/sites-enabled/*.caddy
EOF

# Keeps the import glob non-empty so Caddy never fails on an empty directory
echo "# Public sites are enabled with: shadenet-ctl sites-enable" \
  > "${CONFIG_DIR}/caddy/sites-enabled/00-placeholder.caddy"

cat > "${CONFIG_DIR}/caddy/sites-available/public.caddy" <<EOF
# ShadeNet front door + Matrix delegation for @user:${MATRIX_SERVER_NAME}
${MATRIX_SERVER_NAME}, www.${MATRIX_SERVER_NAME}, shady.example.org {
    encode gzip zstd
    header {
        Strict-Transport-Security "max-age=31536000"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        -Server
    }
    handle /.well-known/matrix/server {
        header Content-Type application/json
        respond \`{"m.server": "${MATRIX_HOST}:443"}\`
    }
    handle /.well-known/matrix/client {
        header Content-Type application/json
        header Access-Control-Allow-Origin *
        respond \`{"m.homeserver": {"base_url": "https://${MATRIX_HOST}"}}\`
    }
    handle {
        # Egg: shadenet-core is not built yet — 502 until it is
        reverse_proxy shadenet-core:8765
    }
}

# Matrix Synapse homeserver (client + federation over 443)
${MATRIX_HOST} {
    encode gzip zstd
    header -Server
    # Admin API is never public — use: shadenet-ctl matrix-admin ...
    @admin path /_synapse/admin*
    respond @admin 404
    reverse_proxy matrix-synapse:8008
}

# Element web client
${CHAT_HOST} {
    encode gzip zstd
    header {
        Strict-Transport-Security "max-age=31536000"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        Referrer-Policy "strict-origin-when-cross-origin"
        -Server
    }
    reverse_proxy element-web:8080
}
EOF

echo "===> [4/8] Writing Synapse homeserver config (registration closed)..."
SYN_DIR="${DATA_DIR}/synapse"
if [ ! -f "${SYN_DIR}/homeserver.yaml" ]; then
  cat > "${SYN_DIR}/homeserver.yaml" <<EOF
server_name: "${MATRIX_SERVER_NAME}"
public_baseurl: "https://${MATRIX_HOST}/"
pid_file: /data/homeserver.pid

listeners:
  - port: 8008
    tls: false
    type: http
    x_forwarded: true
    bind_addresses: ['0.0.0.0']
    resources:
      - names: [client, federation]
        compress: false

database:
  name: psycopg2
  args:
    user: synapse
    password: "${POSTGRES_PASSWORD}"
    dbname: synapse
    host: matrix-postgres
    cp_min: 5
    cp_max: 10

log_config: "/data/log.config"
media_store_path: /data/media_store
signing_key_path: "/data/${MATRIX_SERVER_NAME}.signing.key"
trusted_key_servers:
  - server_name: "matrix.org"
suppress_key_server_warning: true
report_stats: false

# Accounts are created by the operator only (shadenet-ctl matrix-create-admin)
enable_registration: false
registration_shared_secret: "${SYNAPSE_REGISTRATION_SECRET}"
macaroon_secret_key: "${SYNAPSE_MACAROON_SECRET}"
form_secret: "${SYNAPSE_FORM_SECRET}"

# Privacy & disk discipline
url_preview_enabled: false
allow_public_rooms_over_federation: false
allow_public_rooms_without_auth: false
require_auth_for_profile_requests: true
limit_profile_requests_to_users_who_share_rooms: true
max_upload_size: 50M
media_retention:
  remote_media_lifetime: 90d
EOF

  cat > "${SYN_DIR}/log.config" <<'EOF'
version: 1
formatters:
  precise:
    format: '%(asctime)s - %(name)s - %(lineno)d - %(levelname)s - %(message)s'
handlers:
  console:
    class: logging.StreamHandler
    formatter: precise
loggers:
  synapse.storage.SQL:
    level: WARNING
root:
  level: INFO
  handlers: [console]
disable_existing_loggers: false
EOF
  chown "${SYNAPSE_UID}:${SYNAPSE_UID}" "${SYN_DIR}/homeserver.yaml" "${SYN_DIR}/log.config"
  chmod 600 "${SYN_DIR}/homeserver.yaml"
fi

echo "===> [5/8] Writing Element web client config..."
cat > "${CONFIG_DIR}/element/config.json" <<EOF
{
  "default_server_config": {
    "m.homeserver": {
      "base_url": "https://${MATRIX_HOST}",
      "server_name": "${MATRIX_SERVER_NAME}"
    }
  },
  "disable_custom_urls": true,
  "disable_guests": true,
  "brand": "ShadeNet Chat",
  "default_theme": "dark",
  "show_labs_settings": false,
  "room_directory": { "servers": ["${MATRIX_SERVER_NAME}"] }
}
EOF
chmod 644 "${CONFIG_DIR}/element/config.json"

echo "===> [6/8] Writing Tor image and onion service config..."
cat > "${CONFIG_DIR}/tor/Dockerfile" <<EOF
FROM ${ALPINE_IMAGE}
RUN apk add --no-cache tor su-exec
COPY entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
EOF

cat > "${CONFIG_DIR}/tor/entrypoint.sh" <<'EOF'
#!/bin/sh
# Tor refuses to run unless its DataDirectory is private and owned by it
set -e
chown -R tor:tor /var/lib/tor
chmod 700 /var/lib/tor
exec su-exec tor tor -f /etc/tor/torrc
EOF

cat > "${CONFIG_DIR}/tor/torrc" <<EOF
SOCKSPort 0.0.0.0:9050
SocksPolicy accept ${EDGE_SUBNET}
SocksPolicy reject *

ORPort 0
ExitRelay 0
ExitPolicy reject *:*

DataDirectory /var/lib/tor

# Onion Service: ShadeNet (via Caddy's onion ingress on :8080)
HiddenServiceDir /var/lib/tor/shadenet_service/
HiddenServiceVersion 3
HiddenServicePort 80 ${CADDY_EDGE_IP}:8080
EOF
# Read by the unprivileged tor user inside the container
chmod 644 "${CONFIG_DIR}/tor/torrc"

echo "===> [7/8] Writing compose.yaml..."
cat > "${COMPOSE_FILE}" <<EOF
name: shadenet

networks:
  edge:
    driver: bridge
    ipam:
      config:
        - subnet: ${EDGE_SUBNET}
  matrix-net:
    driver: bridge
    internal: true

x-hardening: &hardening
  restart: always
  security_opt:
    - no-new-privileges:true
  labels:
    autoheal: "true"

services:
  # ==========================================================================
  # 1. INGRESS: the ONLY container publishing ports (80/443)
  # ==========================================================================
  ingress:
    <<: *hardening
    image: ${CADDY_IMAGE}
    container_name: shadenet_ingress
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./config/caddy/Caddyfile:/etc/caddy/Caddyfile:ro
      - ./config/caddy/sites-enabled:/etc/caddy/sites-enabled:ro
      - ./config/caddy/sites-available:/etc/caddy/sites-available:ro
      - ./data/caddy_data:/data
      - ./data/caddy_config:/config
      - ./logs/caddy:/var/log/caddy
    networks:
      edge:
        ipv4_address: ${CADDY_EDGE_IP}
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://127.0.0.1:8080/"]
      interval: 15s
      timeout: 5s
      retries: 3

  # ==========================================================================
  # 2. MATRIX SYNAPSE (server_name ${MATRIX_SERVER_NAME}; no host ports)
  # ==========================================================================
  matrix-synapse:
    <<: *hardening
    image: ${SYNAPSE_IMAGE}
    container_name: matrix_synapse
    depends_on:
      matrix-postgres:
        condition: service_healthy
    environment:
      SYNAPSE_CONFIG_PATH: /data/homeserver.yaml
    volumes:
      - ./data/synapse:/data
    networks:
      - edge
      - matrix-net
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8008/health || exit 1"]
      interval: 20s
      timeout: 5s
      retries: 3
      start_period: 60s

  # ==========================================================================
  # 3. MATRIX POSTGRES (internal network only)
  # ==========================================================================
  matrix-postgres:
    <<: *hardening
    image: ${POSTGRES_IMAGE}
    container_name: matrix_postgres
    environment:
      POSTGRES_USER: synapse
      POSTGRES_PASSWORD: "\${POSTGRES_PASSWORD}"
      POSTGRES_DB: synapse
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8 --lc-collate=C --lc-ctype=C"
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
    networks:
      - matrix-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U synapse -d synapse"]
      interval: 10s
      timeout: 5s
      retries: 3

  # ==========================================================================
  # 4. ELEMENT WEB (no host ports)
  # ==========================================================================
  element-web:
    <<: *hardening
    image: ${ELEMENT_IMAGE}
    container_name: element_web
    environment:
      # Unprivileged port: no-new-privileges blocks nginx's file capability for :80
      ELEMENT_WEB_PORT: 8080
    volumes:
      - ./config/element/config.json:/app/config.json:ro
    networks:
      - edge
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://127.0.0.1:8080/"]
      interval: 20s
      timeout: 5s
      retries: 3

  # ==========================================================================
  # 5. TOR (SOCKS for the edge network + ShadeNet onion service)
  # ==========================================================================
  tor:
    <<: *hardening
    build:
      context: ./config/tor
    image: shadenet/tor:local
    container_name: shadenet_tor
    volumes:
      - ./config/tor/torrc:/etc/tor/torrc:ro
      - ./data/tor:/var/lib/tor
    networks:
      - edge

  # ==========================================================================
  # 6. AUTOHEAL: restarts containers whose healthcheck fails
  # ==========================================================================
  autoheal:
    image: ${AUTOHEAL_IMAGE}
    container_name: shadenet_autoheal
    restart: always
    security_opt:
      - no-new-privileges:true
    environment:
      AUTOHEAL_CONTAINER_LABEL: autoheal
      AUTOHEAL_INTERVAL: 10
      AUTOHEAL_START_PERIOD: 60
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    network_mode: none

  # ==========================================================================
  # EGG: shadenet-core — uncomment when the ShadeNet image is ready
  # ==========================================================================
  # shadenet-core:
  #   <<: *hardening
  #   build:
  #     context: /opt/shadenet
  #   container_name: shadenet_core
  #   environment:
  #     SHADENET_DB: /data/shadenet/shadenet.db
  #     NIGHTCAL_PORT: 8765
  #     NIGHTCAL_HOST: 0.0.0.0
  #     NIGHTCAL_BEARER: "\${NIGHTCAL_BEARER}"
  #   volumes:
  #     - ./data/shadenet:/data/shadenet
  #     - ./logs/shadenet:/var/log/shadenet
  #   networks:
  #     - edge
  #   healthcheck:
  #     test: ["CMD-SHELL", "curl -fsS http://localhost:8765/api/health || exit 1"]
  #     interval: 20s
  #     timeout: 5s
  #     retries: 3
EOF

echo "===> [8/8] Pulling images, building Tor, generating Synapse signing key..."
cd "${ROOT_DIR}"
docker compose config --quiet
docker compose pull --ignore-buildable
docker compose build

if [ ! -f "${SYN_DIR}/${MATRIX_SERVER_NAME}.signing.key" ]; then
  docker compose run --rm --no-deps --user "${SYNAPSE_UID}:${SYNAPSE_UID}" \
    --entrypoint python matrix-synapse \
    -m synapse.app.homeserver --config-path /data/homeserver.yaml --generate-keys
fi

echo "✓ Nest compose stack prepared at ${ROOT_DIR} (public sites staged, not enabled)"
