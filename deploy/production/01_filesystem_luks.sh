#!/usr/bin/env bash
# ==============================================================================
# 01_filesystem_luks.sh — Standardized Filesystem & Encryption-at-Rest (LUKS2)
# Target: Fresh production VPS (Debian 12 / Ubuntu 24.04)
# ==============================================================================
set -euo pipefail

ROOT_DIR="/srv/shadenet"
DATA_DIR="${ROOT_DIR}/data"
VAULT_IMG="/var/lib/shadenet-vault.img"
VAULT_MAPPER="shadenet-vault"
VAULT_KEY="/etc/security/luks/shadenet.key"
VAULT_SIZE_GB="${VAULT_SIZE_GB:-80}"

echo "===> [1/4] Installing cryptsetup and filesystem utilities..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq cryptsetup e2fsprogs udev

echo "===> [2/4] Setting up clean standardized filesystem structure in ${ROOT_DIR}..."
mkdir -p "${ROOT_DIR}"/{bin,config,logs,backups}
mkdir -p "${ROOT_DIR}/config"/{caddy,synapse,postgres,monero,unbound,wireguard,tor}
mkdir -p "${ROOT_DIR}/logs"/{caddy,synapse,monero,shadenet,unbound,wireguard,repairs}
mkdir -p /etc/security/luks

echo "===> [3/4] Initializing LUKS2 encrypted-at-rest data vault (${VAULT_SIZE_GB}GB)..."
if [ ! -f "${VAULT_KEY}" ]; then
  # Generate 512-bit cryptographic master key for unattended systemd unlock
  openssl rand -out "${VAULT_KEY}" 64
  chmod 400 "${VAULT_KEY}"
  chown root:root "${VAULT_KEY}"
fi

if [ ! -f "${VAULT_IMG}" ]; then
  echo "Allocating sparse vault container image: ${VAULT_IMG} (${VAULT_SIZE_GB}GB)..."
  # Use fallocate for fast allocation, fallback to truncate if sparse
  fallocate -l "${VAULT_SIZE_GB}G" "${VAULT_IMG}" || truncate -s "${VAULT_SIZE_GB}G" "${VAULT_IMG}"
  chmod 600 "${VAULT_IMG}"

  echo "Formatting container with LUKS2 (AES-XTS 512-bit)..."
  cryptsetup luksFormat --type luks2 --cipher aes-xts-plain64 --key-size 512 --pbkdf argon2id \
    --batch-mode "${VAULT_IMG}" "${VAULT_KEY}"

  echo "Opening LUKS volume..."
  cryptsetup open "${VAULT_IMG}" "${VAULT_MAPPER}" --key-file "${VAULT_KEY}"

  echo "Formatting ext4 filesystem inside encrypted container..."
  mkfs.ext4 -q -L shadenet-vault "/dev/mapper/${VAULT_MAPPER}"
fi

# Ensure volume is open
if [ ! -e "/dev/mapper/${VAULT_MAPPER}" ]; then
  cryptsetup open "${VAULT_IMG}" "${VAULT_MAPPER}" --key-file "${VAULT_KEY}"
fi

# Ensure data directory exists and mount volume
mkdir -p "${DATA_DIR}"
if ! mountpoint -q "${DATA_DIR}"; then
  mount "/dev/mapper/${VAULT_MAPPER}" "${DATA_DIR}"
fi

# Persist to /etc/crypttab and /etc/fstab for clean auto-unlock on reboot
if ! grep -q "${VAULT_MAPPER}" /etc/crypttab 2>/dev/null; then
  echo "${VAULT_MAPPER} ${VAULT_IMG} ${VAULT_KEY} luks,discard" >> /etc/crypttab
fi

if ! grep -q "${DATA_DIR}" /etc/fstab 2>/dev/null; then
  echo "/dev/mapper/${VAULT_MAPPER} ${DATA_DIR} ext4 defaults,noatime,nodiratime 0 2" >> /etc/fstab
fi

echo "===> [4/4] Creating encrypted subdirectories for individual services..."
mkdir -p "${DATA_DIR}"/{postgres,synapse,monero,shadenet,tor,wireguard}
chmod 700 "${DATA_DIR}"/*

echo "✓ Filesystem standardized and LUKS2 encryption-at-rest active at ${DATA_DIR}"
