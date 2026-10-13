#!/usr/bin/env bash
# ==============================================================================
# 01_filesystem.sh — Standardized Filesystem Layout
# Target: Fresh production VPS (Debian 12 / Ubuntu 24.04+)
#
# Encryption at rest is NOT done here. The stack is provisioned and verified
# unencrypted first; run 07_encrypt_at_rest.sh afterwards to migrate
# /srv/shadenet/data into a LUKS2 vault with Tang auto-unlock.
# ==============================================================================
set -euo pipefail

ROOT_DIR="/srv/shadenet"
DATA_DIR="${ROOT_DIR}/data"

# UID the matrixdotorg/synapse image drops to
SYNAPSE_UID=991

echo "===> [1/2] Setting up clean standardized filesystem structure in ${ROOT_DIR}..."
mkdir -p "${ROOT_DIR}"/{bin,config,logs,backups}
mkdir -p "${ROOT_DIR}/config"/{caddy,synapse,element,unbound,wireguard,tor}
mkdir -p "${ROOT_DIR}/logs"/{caddy,synapse,shadenet,unbound,wireguard,repairs}
chmod 700 "${ROOT_DIR}/config"

echo "===> [2/2] Creating data subdirectories for individual services..."
mkdir -p "${DATA_DIR}"/{postgres,synapse,shadenet,tor,caddy_data,caddy_config}
chmod 700 "${DATA_DIR}"/*

# Synapse runs unprivileged and must own its data dir
chown -R "${SYNAPSE_UID}:${SYNAPSE_UID}" "${DATA_DIR}/synapse"

echo "✓ Filesystem standardized at ${ROOT_DIR} (unencrypted — run 07_encrypt_at_rest.sh once stack is verified)"
