#!/usr/bin/env bash
# ==============================================================================
# 06_backup_sync.sh — Encrypted, Append-Only Backups to the backup host (borg)
# Target: Production VPS. Pair with backup_host.sh (run ON backup-host).
#
# MODEL:
# - borg repokey-blake2: authenticated encryption, dedup, compression.
# - Production logs in as 'shadenet-backup' whose key is forced to
#   `borg serve --append-only`: a compromised production server can add
#   archives but cannot destroy history.
# - Postgres is streamed straight into borg — no plaintext dumps on disk.
# - Failures FAIL (systemd unit goes red, shadenet-ctl backup-status shows it).
#
# Order of operations:
#   1. This script (generates SSH key + passphrase, installs timer).
#   2. On backup-host: PROD_PUBKEY='<printed key>' bash backup_host.sh
#   3. Here: shadenet-ctl backup-now   (first run initialises the repo)
# ==============================================================================
set -euo pipefail

ROOT_DIR="/srv/shadenet"
: "${BACKUP_HOST:?Set BACKUP_HOST}"
BACKUP_USER="shadenet-backup"
BORG_REPO_URL="ssh://${BACKUP_USER}@${BACKUP_HOST}/srv/borg/shadenet"
SECRETS_DIR="/root/.config/shadenet"
SSH_KEY="/root/.ssh/shadenet_backup_ed25519"
KNOWN_HOSTS="/root/.ssh/known_hosts_backup"
# Optional: pin backup-host's host key line (from a trusted known_hosts) instead of TOFU
BACKUP-HOST_HOSTKEY="${BACKUP-HOST_HOSTKEY:-}"

echo "===> [1/4] Installing borg..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq borgbackup openssh-client

echo "===> [2/4] Generating backup SSH key and repository passphrase..."
mkdir -p "${SECRETS_DIR}" /root/.ssh
chmod 700 "${SECRETS_DIR}" /root/.ssh
if [ ! -f "${SSH_KEY}" ]; then
  ssh-keygen -q -t ed25519 -N "" -C "shadenet-backup@$(hostname)" -f "${SSH_KEY}"
fi
if [ ! -f "${SECRETS_DIR}/borg-passphrase" ]; then
  ( umask 077; openssl rand -base64 48 | tr -d '\n' > "${SECRETS_DIR}/borg-passphrase" )
fi
if [ ! -s "${KNOWN_HOSTS}" ]; then
  if [ -n "${BACKUP-HOST_HOSTKEY}" ]; then
    echo "${BACKUP-HOST_HOSTKEY}" > "${KNOWN_HOSTS}"
  else
    ssh-keyscan -t ed25519 "${BACKUP_HOST}" > "${KNOWN_HOSTS}" 2>/dev/null
    echo "!! backup-host host key pinned by first contact (TOFU). Verify:"
    ssh-keygen -lf "${KNOWN_HOSTS}"
  fi
fi

echo "===> [3/4] Writing backup script (${ROOT_DIR}/bin/backup.sh)..."
cat > "${ROOT_DIR}/bin/backup.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail

export BORG_REPO="${BORG_REPO_URL}"
export BORG_PASSCOMMAND="cat ${SECRETS_DIR}/borg-passphrase"
export BORG_RSH="ssh -i ${SSH_KEY} -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=${KNOWN_HOSTS} -o ControlMaster=auto -o ControlPath=/run/shadenet-backup-%C -o ControlPersist=120"
# ^ one multiplexed connection: backup-host rate-limits new SSH connections to 6/min
ROOT_DIR="${ROOT_DIR}"
EOF
cat >> "${ROOT_DIR}/bin/backup.sh" <<'EOF'

# borg: 0 = ok, 1 = warning (e.g. file changed while reading), >=2 = error
borg_run() {
  local rc=0
  borg "$@" || rc=$?
  if [ "${rc}" -ge 2 ]; then
    echo "borg $1 FAILED (rc=${rc})" >&2
    exit "${rc}"
  fi
}

# First run: create the repository (append-only server side still allows init)
if ! borg info >/dev/null 2>&1; then
  echo "[*] Initialising borg repository on backup-host..."
  borg init --encryption=repokey-blake2
  ( umask 077; borg key export "${BORG_REPO}" /root/shadenet-borg-key.txt )
  echo "!! Copy /root/shadenet-borg-key.txt and ${HOME}/.config/shadenet/borg-passphrase"
  echo "!! to the operator laptop, then: shred -u /root/shadenet-borg-key.txt"
fi

echo "[*] Streaming Matrix Postgres dump into borg..."
if docker ps -q -f name=^matrix_postgres$ | grep -q .; then
  borg_run create --stats --compression zstd,6 \
    --content-from-command --stdin-name synapse.sql \
    "::{hostname}-db-{now:%Y-%m-%dT%H:%M:%S}" \
    -- docker exec matrix_postgres pg_dump -U synapse --no-owner synapse
else
  echo "matrix_postgres is not running — refusing to report a partial backup as success." >&2
  exit 2
fi

echo "[*] Archiving data, config, secrets..."
borg_run create --stats --compression zstd,6 --one-file-system \
  --exclude "${ROOT_DIR}/data/postgres" \
  --exclude "${ROOT_DIR}/data/synapse/media_store/remote_content" \
  --exclude "${ROOT_DIR}/data/synapse/media_store/remote_thumbnail" \
  --exclude "${ROOT_DIR}/data.plaintext-old" \
  "::{hostname}-files-{now:%Y-%m-%dT%H:%M:%S}" \
  "${ROOT_DIR}/data" "${ROOT_DIR}/config" "${ROOT_DIR}/.env" /etc/wireguard

# Append-only: prune only MARKS archives deleted; backup-host decides when to compact
echo "[*] Pruning (append-only — reversible until backup-host compacts)..."
borg_run prune --glob-archives '{hostname}-db-*' --keep-daily 14 --keep-weekly 8 --keep-monthly 6
borg_run prune --glob-archives '{hostname}-files-*' --keep-daily 14 --keep-weekly 8 --keep-monthly 6

echo "[✓] Backup complete."
EOF
chmod 700 "${ROOT_DIR}/bin/backup.sh"

echo "===> [4/4] Installing daily systemd backup timer (03:00 UTC)..."
# Replace the old unit name if an earlier version installed it
systemctl disable --now steward-backup.timer 2>/dev/null || true
rm -f /etc/systemd/system/steward-backup.{service,timer}

cat > /etc/systemd/system/shadenet-backup.service <<EOF
[Unit]
Description=ShadeNet encrypted append-only backup to backup-host
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=${ROOT_DIR}/bin/backup.sh
Nice=10
IOSchedulingClass=idle
EOF

cat > /etc/systemd/system/shadenet-backup.timer <<'EOF'
[Unit]
Description=Daily ShadeNet backup

[Timer]
OnCalendar=*-*-* 03:00:00 UTC
RandomizedDelaySec=1800
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now shadenet-backup.timer

echo "======================================================================"
echo " ✓ Backup timer installed. Backups are NOT active until backup-host trusts"
echo "   this key. On backup-host run:"
echo ""
echo "   PROD_PUBKEY='$(cat "${SSH_KEY}.pub")' bash backup_host.sh"
echo ""
echo "   then here: shadenet-ctl backup-now"
echo "======================================================================"
