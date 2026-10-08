# Shadenet (A place in the shade) — multi-stage Dockerfile (TASK-02)
#
# Stages:
#   build   — compile the canonical Shadenet package into an installable form
#             and copy the artifacts into the image.
#   runtime — Python 3.11+, SQLite, Caddy (TLS front door), Tor (darknet .onion),
#             the canonical Shadenet package, and the bootstrap entry.
#
# All secrets come from the environment (docker-compose.yml) — never committed.
# The SQLite database is generated on first boot by shadenet.entry:
#   - when SHADENET_LAT / SHADENET_LON / SHADENET_RADIUS_KM are set, the box
#     computes the bounding box, queries OSM Overpass, and populates SQLite;
#   - otherwise the existing shadenet.db is used.
#
# Usage:
#   docker build -t shadenet:latest -f Dockerfile .
#   docker compose up -d

# ---------------------------------------------------------------- build ----
FROM python:3.11-slim AS build
WORKDIR /tmp/build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libsqlite3-dev \
    curl \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy the canonical Shadenet package so it can be installed and its artifacts
# (requirements.txt, compiled zine, AVR graph) collected.
COPY shadenet/ ./shadenet/
RUN printf 'pyyaml\n' > requirements.txt \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -e . \
    && pip install --no-cache-dir -e .[dev] 2>/dev/null || true \
    && rm -rf /root/.cache/pip

# -------------------------------------------------------------- runtime ----
FROM python:3.11-slim AS runtime
LABEL org.opencontainers.image.title="Shadenet" \
      org.opencontainers.image.description="Autonomous, privacy-first cited intelligence for night culture" \
      org.opencontainers.image.version="0.1.0"

# Runtime system deps: SQLite, Caddy (TLS front door), Tor (darknet .onion).
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    curl \
    gnupg \
    ca-certificates \
    lsb-release \
    && curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg \
    && curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        caddy \
        tor \
    && rm -rf /var/lib/apt/lists/* \
    && caddy version

RUN pip install --no-cache-dir pyyaml rapidfuzz requests httpx python-frontmatter

WORKDIR /app

# Canonical Shadenet package, copied in from the build stage.
COPY --from=build /tmp/build/shadenet /app/shadenet

# Declarative config (env-driven; never commit real secrets).
RUN mkdir -p /data /var/log/shadenet /etc/shadenet /var/lib/tor/shadenet \
    && chmod 700 /var/lib/tor/shadenet

COPY config/caddyfile.caddyconf /etc/shadenet/Caddyfile
COPY config/torrc /etc/tor/torrc
COPY config/shadenet.env.example /etc/shadenet/.env.example
RUN chmod 600 /etc/shadenet/.env.example

# Bootstrap + sync mesh.
COPY shadenet/entry.py /app/entry.py
COPY shadenet/sync_mesh.py /app/sync_mesh.py
RUN chmod +x /app/entry.py /app/sync_mesh.py

# Static PWA assets for the Steward (manifest + service worker + index).
COPY shadenet/nightcal/static /app/shadenet/static

VOLUME ["/data", "/var/lib/tor/shadenet", "/var/log/shadenet"]

# Environment of record (shell-escaped in docker-compose.yml; never committed).
ENV SHADENET_DB=/data/shadenet.db \
    NIGHTCAL_PORT=8765 \
    NIGHTCAL_HOST=0.0.0.0 \
    SHADENET_DEV_MODE=0 \
    SHADENET_LAT= \
    SHADENET_LON= \
    SHADENET_RADIUS_KM=

EXPOSE 80/tcp 8765/tcp 8766/tcp

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -fsS http://localhost:8765/ || exit 1

# Bootstrap entrypoint: shadenet | fill | server | zine
ENTRYPOINT ["python3", "/app/entry.py"]
