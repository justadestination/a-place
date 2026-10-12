#!/usr/bin/env bash
# ==============================================================================
# 04_containers_compose.sh — Isolated Multi-Container Stack & Single Ingress
# Target: Fresh production VPS (Debian 12 / Ubuntu 24.04)
#
# ARCHITECTURE:
# - Single Ingress: Caddy container is the ONLY container with public ports (80/443).
# - Zero Exposed Ports: Postgres, Synapse, ShadeNet, Monero have NO public port bindings.
# - Storage: All persistent volumes mounted to /srv/shadenet/data (LUKS2 Encrypted).
# - Isolated Bridge Networks: ingress-net, matrix-net, monero-net, tor-net.
# - Automated Self-Healing: willfarrell/autoheal monitors container healthchecks.
# ==============================================================================
set -euo pipefail

ROOT_DIR="/srv/shadenet"
CONFIG_DIR="${ROOT_DIR}/config"
DATA_DIR="${ROOT_DIR}/data"
LOGS_DIR="${ROOT_DIR}/logs"
COMPOSE_FILE="${ROOT_DIR}/compose.yaml"
ENV_FILE="${ROOT_DIR}/.env"
SERVER_VPN_IP="203.0.113.1"

echo "===> [1/6] Installing Docker Engine and Compose Plugin..."
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sh /tmp/get-docker.sh
  rm -f /tmp/get-docker.sh
  systemctl enable docker
  systemctl start docker
fi

echo "===> [2/6] Generating cryptographically secure secrets in ${ENV_FILE}..."
if [ ! -f "${ENV_FILE}" ]; then
  cat > "${ENV_FILE}" <<EOF
# ShadeNet Production Environment Secrets
POSTGRES_PASSWORD=$(openssl rand -hex 16)
SYNAPSE_REGISTRATION_SECRET=$(openssl rand -hex 24)
SYNAPSE_MACAROON_SECRET=$(openssl rand -hex 24)
SYNAPSE_FORM_SECRET=$(openssl rand -hex 24)
MONERO_RPC_USER=steward_operator
MONERO_RPC_PASSWORD=$(openssl rand -hex 16)
SHADENET_SECRET_KEY=$(openssl rand -hex 32)
NIGHTCAL_BEARER=$(openssl rand -hex 24)
DOMAIN_NAME=example.org
SERVER_VPN_IP=${SERVER_VPN_IP}
EOF
  chmod 600 "${ENV_FILE}"
fi

# Load variables into environment for templating
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

echo "===> [3/6] Setting up Caddyfile (Single Public Ingress)..."
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

# Web Chat Client (Element Web)
chat.example.org {
    reverse_proxy element-web:80
    encode gzip zstd
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        Referrer-Policy "strict-origin-when-cross-origin"
    }
}

# Matrix Synapse Homeserver
matrix.example.org {
    encode gzip zstd

    # Matrix Well-Known Delegation
    handle /.well-known/matrix/server {
        header Content-Type application/json
        header Access-Control-Allow-Origin *
        respond "{\"m.server\": \"matrix.example.org:443\"}"
    }
    handle /.well-known/matrix/client {
        header Content-Type application/json
        header Access-Control-Allow-Origin *
        respond "{\"m.homeserver\": {\"base_url\": \"https://matrix.example.org\"}}"
    }

    # All API and Federation Traffic to Synapse
    reverse_proxy matrix-synapse:8008 {
        header_up X-Forwarded-Proto https
        header_up X-Forwarded-For {remote_host}
    }
}

# ShadeNet NightCal & Zine Front Door
shady.example.org {
    reverse_proxy shadenet-core:8765
    encode gzip zstd
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
    }
}

# WireGuard Internal Discovery Ingress (203.0.113.1)
http://${SERVER_VPN_IP} {
    respond "ShadeNet Management Ingress (WireGuard Secured)" 200
}
EOF

echo "===> [4/6] Setting up Monero container build files..."
mkdir -p "${CONFIG_DIR}/monero"
cat > "${CONFIG_DIR}/monero/Dockerfile" <<'EOF'
FROM debian:12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    bzip2 curl ca-certificates libzmq3-dev libunbound-dev \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1000 monero && useradd -u 1000 -g monero -m monero
WORKDIR /opt/monero

ENV MONERO_VERSION="0.18.3.4"
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then M_ARCH="x64"; \
    elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then M_ARCH="armv8"; \
    else echo "Unsupported arch: $ARCH" && exit 1; fi && \
    (curl -fsSL "https://downloads.getmonero.org/cli/monero-linux-${M_ARCH}-v${MONERO_VERSION}.tar.bz2" -o monero.tar.bz2 \
     || curl -fsSL "https://github.com/monero-project/monero/releases/download/v${MONERO_VERSION}/monero-linux-${M_ARCH}-v${MONERO_VERSION}.tar.bz2" -o monero.tar.bz2) \
    && tar -xjf monero.tar.bz2 -C /opt/monero --strip-components=1 \
    && rm -f monero.tar.bz2 \
    && chmod +x /opt/monero/monerod /opt/monero/monero-wallet-rpc \
    && ln -s /opt/monero/monerod /usr/local/bin/monerod \
    && ln -s /opt/monero/monero-wallet-rpc /usr/local/bin/monero-wallet-rpc

USER monero
WORKDIR /var/lib/monero
EOF

echo "===> [5/6] Writing Master compose.yaml (All Services Containerized)..."
cat > "${COMPOSE_FILE}" <<EOF
version: "3.8"

networks:
  ingress-net:
    driver: bridge
  matrix-net:
    driver: bridge
    internal: true
  monero-net:
    driver: bridge
    internal: true
  tor-net:
    driver: bridge

services:
  # ============================================================================
  # 1. INGRESS: The ONLY container exposing public ports (80/443)
  # ============================================================================
  ingress:
    image: caddy:2.9-alpine
    container_name: shadenet_ingress
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./config/caddy/Caddyfile:/etc/caddy/Caddyfile:ro
      - ./data/caddy_data:/data
      - ./data/caddy_config:/config
      - ./logs/caddy:/var/log/caddy
    networks:
      - ingress-net
    healthcheck:
      test: ["CMD", "caddy", "version"]
      interval: 15s
      timeout: 5s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"

  # ============================================================================
  # 2. MATRIX SYNAPSE HOMESERVER (Zero public port exposure)
  # ============================================================================
  matrix-synapse:
    image: matrixdotorg/synapse:latest
    container_name: matrix_synapse
    restart: always
    depends_on:
      matrix-postgres:
        condition: service_healthy
    environment:
      SYNAPSE_CONFIG_PATH: /data/homeserver.yaml
    volumes:
      - ./data/synapse:/data
      - ./logs/synapse:/var/log/synapse
    networks:
      - ingress-net
      - matrix-net
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8008/health || exit 1"]
      interval: 20s
      timeout: 5s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"

  # ============================================================================
  # 3. MATRIX POSTGRESQL (Strictly internal to matrix-net, encrypted at rest)
  # ============================================================================
  matrix-postgres:
    image: postgres:16-alpine
    container_name: matrix_postgres
    restart: always
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

  # ============================================================================
  # 4. ELEMENT WEB CLIENT (Zero public port exposure)
  # ============================================================================
  element-web:
    image: vectorim/element-web:latest
    container_name: element_web
    restart: always
    networks:
      - ingress-net
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:80"]
      interval: 20s
      timeout: 5s
      retries: 3

  # ============================================================================
  # 5. MONERO FULL NODE (Pruned, Outbound P2P only, Tx routed via Tor)
  # ============================================================================
  monerod:
    build:
      context: ./config/monero
    container_name: monero_node
    restart: always
    command: >
      monerod
      --data-dir=/var/lib/monero/data
      --prune-blockchain
      --rpc-bind-ip=0.0.0.0
      --rpc-bind-port=18081
      --restricted-rpc
      --confirm-external-bind
      --no-igd
      --in-peers=0
      --out-peers=32
      --tx-proxy=tor,tor:9050
      --non-interactive
    volumes:
      - ./data/monero:/var/lib/monero
      - ./logs/monero:/var/log/monero
    networks:
      - monero-net
      - tor-net
    # Expose restricted RPC strictly to WireGuard VPN IP (203.0.113.1) for operator
    ports:
      - "${SERVER_VPN_IP}:18081:18081"
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:18081/get_height || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ============================================================================
  # 6. MONERO WALLET RPC (Zero public port exposure)
  # ============================================================================
  monero-wallet-rpc:
    build:
      context: ./config/monero
    container_name: monero_wallet_rpc
    restart: always
    depends_on:
      - monerod
    command: >
      monero-wallet-rpc
      --daemon-address=monerod:18081
      --rpc-bind-ip=0.0.0.0
      --rpc-bind-port=18082
      --rpc-login=\${MONERO_RPC_USER}:\${MONERO_RPC_PASSWORD}
      --wallet-dir=/var/lib/monero/wallets
      --confirm-external-bind
      --disable-rpc-login=false
      --non-interactive
    volumes:
      - ./data/monero:/var/lib/monero
    networks:
      - monero-net
    # Expose wallet RPC strictly to WireGuard VPN IP (203.0.113.1) for operator
    ports:
      - "${SERVER_VPN_IP}:18082:18082"

  # ============================================================================
  # 7. SHADENET NIGHTCAL & STEWARD CORE (Zero public port exposure)
  # ============================================================================
  shadenet-core:
    build:
      context: /opt/shadenet
      dockerfile: Dockerfile
    container_name: shadenet_core
    restart: always
    environment:
      SHADENET_DB: /data/shadenet/shadenet.db
      NIGHTCAL_PORT: 8765
      NIGHTCAL_HOST: 0.0.0.0
      NIGHTCAL_BEARER: "\${NIGHTCAL_BEARER}"
    volumes:
      - ./data/shadenet:/data/shadenet
      - ./logs/shadenet:/var/log/shadenet
    networks:
      - ingress-net
      - tor-net
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8765/api/health || exit 1"]
      interval: 20s
      timeout: 5s
      retries: 3

  # ============================================================================
  # 8. TOR DAEMON & ONION SERVICES
  # ============================================================================
  tor:
    image: alpine:latest
    container_name: shadenet_tor
    restart: always
    entrypoint: ["sh", "-c", "apk add --no-cache tor && exec tor -f /etc/tor/torrc"]
    volumes:
      - ./config/tor/torrc:/etc/tor/torrc:ro
      - ./data/tor:/var/lib/tor
    networks:
      - tor-net
      - ingress-net

  # ============================================================================
  # 9. AUTOHEAL: Automated Container Repair & Recovery Daemon
  # ============================================================================
  autoheal:
    image: willfarrell/autoheal:latest
    container_name: shadenet_autoheal
    restart: always
    environment:
      AUTOHEAL_CONTAINER_LABEL: all
      AUTOHEAL_INTERVAL: 10
      AUTOHEAL_START_PERIOD: 60
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
EOF

echo "===> [6/6] Writing Tor configuration for container network..."
mkdir -p "${CONFIG_DIR}/tor"
cat > "${CONFIG_DIR}/tor/torrc" <<'EOF'
SOCKSPort 0.0.0.0:9050
SocksPolicy accept 172.16.0.0/12
SocksPolicy accept 127.0.0.1
SocksPolicy reject *

ORPort 0
ExitRelay 0
ExitPolicy reject *:*

DataDirectory /var/lib/tor

# Onion Service: ShadeNet Web & Zine
HiddenServiceDir /var/lib/tor/shadenet_service/
HiddenServiceVersion 3
HiddenServicePort 80 shadenet-core:8765

# Onion Service: Matrix Synapse Homeserver
HiddenServiceDir /var/lib/tor/matrix_service/
HiddenServiceVersion 3
HiddenServicePort 80 matrix-synapse:8008
EOF

chmod 600 "${CONFIG_DIR}/tor/torrc"

echo "✓ Master compose.yaml and container configs generated at ${ROOT_DIR}"
