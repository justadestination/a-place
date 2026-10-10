#!/usr/bin/env bash
# ==============================================================================
# 04_matrix_element.sh — Matrix Synapse Homeserver + PostgreSQL + Element Web
# Target: Fresh production VPS
# ==============================================================================
set -euo pipefail

MATRIX_DOMAIN="example.org"
HOMESERVER_NAME="matrix.example.org"
WEB_CLIENT_DOMAIN="chat.example.org"
MATRIX_DIR="/opt/matrix"
ELEMENT_DIR="/var/www/element"

echo "===> [1/5] Installing Docker Engine & Docker Compose plugin..."
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sh /tmp/get-docker.sh
  rm -f /tmp/get-docker.sh
  systemctl enable docker
  systemctl start docker
fi

echo "===> [2/5] Installing Caddy Web Server..."
if ! command -v caddy &>/dev/null; then
  apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
  apt-get update
  apt-get install -y caddy
  systemctl enable caddy
fi

echo "===> [3/5] Setting up Matrix Synapse & PostgreSQL stack in ${MATRIX_DIR}..."
mkdir -p "${MATRIX_DIR}/data" "${MATRIX_DIR}/postgres"

PG_PASS=$(openssl rand -hex 16)
SYNAPSE_REG_SECRET=$(openssl rand -hex 24)

cat > "${MATRIX_DIR}/docker-compose.yml" <<EOF
version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    container_name: matrix_postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: synapse
      POSTGRES_PASSWORD: "${PG_PASS}"
      POSTGRES_DB: synapse
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8 --lc-collate=C --lc-ctype=C"
    volumes:
      - ./postgres:/var/lib/postgresql/data
    networks:
      - matrix-net

  synapse:
    image: matrixdotorg/synapse:latest
    container_name: matrix_synapse
    restart: unless-stopped
    depends_on:
      - postgres
    environment:
      SYNAPSE_CONFIG_PATH: /data/homeserver.yaml
    volumes:
      - ./data:/data
    ports:
      - "127.0.0.1:8008:8008"
    networks:
      - matrix-net

networks:
  matrix-net:
    driver: bridge
EOF

# Generate initial homeserver.yaml if not present
if [ ! -f "${MATRIX_DIR}/data/homeserver.yaml" ]; then
  docker run -it --rm \
    -v "${MATRIX_DIR}/data:/data" \
    -e SYNAPSE_SERVER_NAME="${HOMESERVER_NAME}" \
    -e SYNAPSE_REPORT_STATS=no \
    matrixdotorg/synapse:latest generate

  # Update database configuration to use PostgreSQL
  cat > "${MATRIX_DIR}/data/homeserver.yaml" <<EOF
server_name: "${HOMESERVER_NAME}"
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
    password: "${PG_PASS}"
    database: synapse
    host: postgres
    cp_min: 5
    cp_max: 10

log_config: "/data/${HOMESERVER_NAME}.log.config"
media_store_path: /data/media_store
registration_shared_secret: "${SYNAPSE_REG_SECRET}"
enable_registration: false
enable_registration_without_verification: false
report_stats: false
macaroon_secret_key: "$(openssl rand -hex 24)"
form_secret: "$(openssl rand -hex 24)"
signing_key_path: "/data/${HOMESERVER_NAME}.signing.key"
trusted_key_servers:
  - server_name: "matrix.org"
EOF
fi

cd "${MATRIX_DIR}" && docker compose up -d

echo "===> [4/5] Deploying Element Web static assets to ${ELEMENT_DIR}..."
mkdir -p "${ELEMENT_DIR}"
ELEMENT_VERSION="v1.11.83"
cd /tmp
wget -q "https://github.com/element-hq/element-web/releases/download/${ELEMENT_VERSION}/element-${ELEMENT_VERSION}.tar.gz" -O element.tar.gz
tar -xzf element.tar.gz -C "${ELEMENT_DIR}" --strip-components=1
rm -f element.tar.gz

cat > "${ELEMENT_DIR}/config.json" <<EOF
{
  "default_server_config": {
    "m.homeserver": {
      "base_url": "https://${HOMESERVER_NAME}",
      "server_name": "${HOMESERVER_NAME}"
    }
  },
  "brand": "Steward NightCal",
  "default_theme": "dark",
  "room_directory": {
    "servers": ["${HOMESERVER_NAME}"]
  }
}
EOF
chown -R www-data:www-data "${ELEMENT_DIR}"

echo "===> [5/5] Configuring Caddy Reverse Proxy & TLS..."
cat > /etc/caddy/Caddyfile <<EOF
# Global Caddy Security & Compression
{
  email ops@example.org
  admin off
}

# Element Web Client
${WEB_CLIENT_DOMAIN} {
  root * ${ELEMENT_DIR}
  file_server
  encode gzip zstd
  header {
    Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
    X-Content-Type-Options "nosniff"
    Referrer-Policy "strict-origin-when-cross-origin"
  }
}

# Matrix Synapse Homeserver API
${HOMESERVER_NAME} {
  encode gzip zstd

  # Well-known delegation
  handle /.well-known/matrix/server {
    header Content-Type application/json
    header Access-Control-Allow-Origin *
    respond "{\"m.server\": \"${HOMESERVER_NAME}:443\"}"
  }
  handle /.well-known/matrix/client {
    header Content-Type application/json
    header Access-Control-Allow-Origin *
    respond "{\"m.homeserver\": {\"base_url\": \"https://${HOMESERVER_NAME}\"}}"
  }

  handle {
    reverse_proxy 127.0.0.1:8008 {
      header_up Host {host}
      header_up X-Forwarded-For {remote_host}
      header_up X-Forwarded-Proto https
    }
  }
}

# Matrix Federation Port 8448
${HOMESERVER_NAME}:8448 {
  reverse_proxy 127.0.0.1:8008 {
    header_up Host {host}
    header_up X-Forwarded-For {remote_host}
    header_up X-Forwarded-Proto https
  }
}

# ShadeNet NightCal Core
shady.example.org {
  encode gzip zstd
  reverse_proxy 127.0.0.1:8765 {
    header_up Host {host}
    header_up X-Forwarded-For {remote_host}
    header_up X-Forwarded-Proto https
  }
}
EOF

systemctl restart caddy
echo "✓ Matrix Synapse, PostgreSQL, Element Web & Caddy reverse proxy deployed and active!"
