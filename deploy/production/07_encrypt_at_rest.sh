#!/usr/bin/env bash
# ==============================================================================
# 07_encrypt_at_rest.sh — Migrate /srv/shadenet/data into a LUKS2 vault
# Target: Production VPS, AFTER provision.sh has run and the stack is verified.
# NOT run by provision.sh — run by hand, once:
#
#   TANG_URL=http://backup-host:7500 TANG_THP=<thumbprint> \
#     bash deploy/production/07_encrypt_at_rest.sh
#
# (tang_host.sh prints the exact command, thumbprint included.)
#
# KEY MODEL:
#   - Keyslot 0: random recovery passphrase -> copy to operator laptop, then
#                shred from the server. Unlocks by hand if Tang is down.
#   - Keyslot 1: Clevis/Tang binding -> auto-unlock at boot, but only while
#                backup-host's Tang is reachable from this server's IP.
#   No key material for the vault is left on this server's disk.
#
# STORAGE:
#   Default is a preallocated image file on the root disk (VAULT_SIZE_GB).
#   Set VAULT_DEVICE=/dev/disk/by-id/scsi-0HC_Volume_XXXX to use a the host
#   Volume instead (recommended once the Monero chain outgrows the root disk).
#   VAULT_DEVICE is WIPED.
#
# DOWNTIME: all containers are stopped while data is copied into the vault.
# ==============================================================================
set -euo pipefail

ROOT_DIR="/srv/shadenet"
DATA_DIR="${ROOT_DIR}/data"
OLD_DATA_DIR="${ROOT_DIR}/data.plaintext-old"
STAGING_MNT="/mnt/shadenet-vault-staging"
VAULT_MAPPER="shadenet-vault"
VAULT_IMG="/var/lib/shadenet-vault.img"
VAULT_DEVICE="${VAULT_DEVICE:-}"
VAULT_SIZE_GB="${VAULT_SIZE_GB:-30}"
VAULT_CONF="/etc/shadenet-vault.conf"
RECOVERY_KEY="/root/shadenet-vault-recovery.key"
TANG_URL="${TANG_URL:?Set TANG_URL (printed by tang_host.sh)}"
TANG_THP="${TANG_THP:?Set TANG_THP (printed by tang_host.sh)}"

STACK_STOPPED=0
on_error() {
  echo "" >&2
  echo "!! Encryption migration FAILED at line $1." >&2
  if [ "${STACK_STOPPED}" = 1 ]; then
    echo "!! The stack is stopped. Original data is untouched in:" >&2
    if [ -d "${OLD_DATA_DIR}" ]; then
      echo "!!   ${OLD_DATA_DIR}  (move it back to ${DATA_DIR} to roll back)" >&2
    else
      echo "!!   ${DATA_DIR}" >&2
    fi
    echo "!! Restart with: systemctl start docker && cd ${ROOT_DIR} && docker compose up -d" >&2
  fi
}
trap 'on_error $LINENO' ERR

echo "===> [1/8] Preflight checks..."
if mountpoint -q "${DATA_DIR}"; then
  echo "${DATA_DIR} is already a mountpoint — vault appears to be in place. Aborting." >&2
  exit 1
fi
if [ -e "${OLD_DATA_DIR}" ]; then
  echo "${OLD_DATA_DIR} exists from a previous run. Inspect and remove it first." >&2
  exit 1
fi
if ! curl -fsS --max-time 10 "${TANG_URL}/adv" >/dev/null; then
  echo "Cannot reach Tang at ${TANG_URL}. Run tang_host.sh and check its firewall." >&2
  exit 1
fi

DATA_USED_GB=$(( $(du -sx --block-size=1G "${DATA_DIR}" | cut -f1) + 1 ))
if [ -z "${VAULT_DEVICE}" ]; then
  # Need room for the full image while the plaintext copy still exists
  FREE_GB=$(df -P --block-size=1G "$(dirname "${VAULT_IMG}")" | awk 'NR==2 {print $4}')
  if [ "${FREE_GB}" -lt "${VAULT_SIZE_GB}" ]; then
    echo "Only ${FREE_GB}G free for a ${VAULT_SIZE_GB}G vault image." >&2
    echo "Lower VAULT_SIZE_GB or attach a the host Volume and set VAULT_DEVICE." >&2
    exit 1
  fi
  if [ $(( DATA_USED_GB * 3 / 2 )) -gt "${VAULT_SIZE_GB}" ]; then
    echo "Data is ${DATA_USED_GB}G; a ${VAULT_SIZE_GB}G vault leaves under 50% headroom." >&2
    echo "Raise VAULT_SIZE_GB or use VAULT_DEVICE." >&2
    exit 1
  fi
else
  if [ ! -b "${VAULT_DEVICE}" ]; then
    echo "VAULT_DEVICE ${VAULT_DEVICE} is not a block device." >&2
    exit 1
  fi
  if findmnt -rno SOURCE | grep -q "^$(readlink -f "${VAULT_DEVICE}")"; then
    echo "VAULT_DEVICE ${VAULT_DEVICE} is mounted. Refusing to wipe it." >&2
    exit 1
  fi
fi

echo "===> [2/8] Installing cryptsetup and Clevis..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq cryptsetup clevis clevis-luks rsync curl

echo "===> [3/8] Generating recovery passphrase (${RECOVERY_KEY})..."
# Printable, no trailing newline: works both as --key-file and when typed by hand
( umask 077; openssl rand -base64 48 | tr -d '\n' > "${RECOVERY_KEY}" )

echo "===> [4/8] Creating LUKS2 vault..."
if [ -n "${VAULT_DEVICE}" ]; then
  VAULT_SOURCE="${VAULT_DEVICE}"
  LUKS_DEV="${VAULT_DEVICE}"
else
  VAULT_SOURCE="${VAULT_IMG}"
  rm -f "${VAULT_IMG}"
  # Real allocation, no sparse fallback: a full disk must fail now, not mid-write later
  fallocate -l "${VAULT_SIZE_GB}G" "${VAULT_IMG}"
  chmod 600 "${VAULT_IMG}"
  LUKS_DEV="$(losetup --find --show "${VAULT_IMG}")"
fi

cryptsetup luksFormat --type luks2 --cipher aes-xts-plain64 --key-size 512 --pbkdf argon2id \
  --batch-mode --key-file "${RECOVERY_KEY}" "${LUKS_DEV}"

echo "===> [5/8] Binding vault to Tang (${TANG_URL}, pinned thumbprint)..."
clevis luks bind -d "${LUKS_DEV}" -k "${RECOVERY_KEY}" tang \
  "{\"url\":\"${TANG_URL}\",\"thp\":\"${TANG_THP}\"}"

# Prove the Tang path works before trusting it with data
clevis luks unlock -d "${LUKS_DEV}" -n "${VAULT_MAPPER}"
mkfs.ext4 -q -L shadenet-vault "/dev/mapper/${VAULT_MAPPER}"
mkdir -p "${STAGING_MNT}"
mount "/dev/mapper/${VAULT_MAPPER}" "${STAGING_MNT}"

echo "===> [6/8] Stopping stack and copying data into vault..."
STACK_STOPPED=1
systemctl stop shadenet-repair.timer shadenet-backup.timer || true
(cd "${ROOT_DIR}" && docker compose down)
systemctl stop docker.socket docker.service

rsync -aHAX --numeric-ids "${DATA_DIR}/" "${STAGING_MNT}/"
# Second pass must report nothing left to transfer
if [ -n "$(rsync -aHAXn --numeric-ids --itemize-changes "${DATA_DIR}/" "${STAGING_MNT}/")" ]; then
  echo "Vault copy does not match ${DATA_DIR}." >&2
  false
fi
umount "${STAGING_MNT}"
rmdir "${STAGING_MNT}"

mv "${DATA_DIR}" "${OLD_DATA_DIR}"
mkdir -p "${DATA_DIR}"
chmod 700 "${OLD_DATA_DIR}"

echo "===> [7/8] Installing boot-time auto-unlock..."
cat > "${VAULT_CONF}" <<EOF
VAULT_SOURCE=${VAULT_SOURCE}
VAULT_MAPPER=${VAULT_MAPPER}
DATA_DIR=${DATA_DIR}
EOF

cat > "${ROOT_DIR}/bin/vault-unlock.sh" <<'EOF'
#!/usr/bin/env bash
# Usage: vault-unlock.sh [auto|manual]
#   auto   — Tang unlock with retries (systemd, at boot)
#   manual — prompts for the recovery passphrase from the operator laptop
set -euo pipefail
# shellcheck disable=SC1091
source /etc/shadenet-vault.conf

MODE="${1:-auto}"
TRIES="${VAULT_UNLOCK_TRIES:-30}"

mountpoint -q "${DATA_DIR}" && exit 0

DEV="${VAULT_SOURCE}"
if [ -f "${VAULT_SOURCE}" ]; then
  DEV="$(losetup -j "${VAULT_SOURCE}" | cut -d: -f1 | head -n1)"
  [ -n "${DEV}" ] || DEV="$(losetup --find --show "${VAULT_SOURCE}")"
fi

if [ ! -e "/dev/mapper/${VAULT_MAPPER}" ]; then
  if [ "${MODE}" = "manual" ]; then
    cryptsetup open "${DEV}" "${VAULT_MAPPER}"
  else
    for i in $(seq 1 "${TRIES}"); do
      clevis luks unlock -d "${DEV}" -n "${VAULT_MAPPER}" && break
      echo "Tang unlock failed (attempt ${i}/${TRIES}), retrying in 10s..." >&2
      sleep 10
    done
    if [ ! -e "/dev/mapper/${VAULT_MAPPER}" ]; then
      echo "Auto-unlock failed. Unlock by hand: shadenet-ctl vault-unlock" >&2
      exit 1
    fi
  fi
fi

mount -o noatime "/dev/mapper/${VAULT_MAPPER}" "${DATA_DIR}"
EOF
chmod 700 "${ROOT_DIR}/bin/vault-unlock.sh"

cat > /etc/systemd/system/shadenet-vault.service <<EOF
[Unit]
Description=ShadeNet encrypted data vault (Tang auto-unlock)
Wants=network-online.target
After=network-online.target
Before=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=${ROOT_DIR}/bin/vault-unlock.sh auto
ExecStop=-/bin/umount ${DATA_DIR}
ExecStop=-/sbin/cryptsetup close ${VAULT_MAPPER}
TimeoutStartSec=10min

[Install]
WantedBy=multi-user.target
EOF

# Docker must never start against the empty unencrypted mountpoint
mkdir -p /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/shadenet-vault.conf <<EOF
[Unit]
Requires=shadenet-vault.service
After=shadenet-vault.service

[Service]
ExecStartPre=/usr/bin/mountpoint -q ${DATA_DIR}
EOF

systemctl daemon-reload
systemctl enable shadenet-vault.service

# Close and reopen through the real boot path to prove it works
cryptsetup close "${VAULT_MAPPER}"
systemctl start shadenet-vault.service
mountpoint -q "${DATA_DIR}"

echo "===> [8/8] Restarting stack on encrypted storage..."
systemctl start docker.socket docker.service
(cd "${ROOT_DIR}" && docker compose up -d)
systemctl start shadenet-repair.timer shadenet-backup.timer
STACK_STOPPED=0

echo "======================================================================"
echo " ✓ ${DATA_DIR} is now a LUKS2 vault with Tang auto-unlock"
echo "======================================================================"
echo " YOU MUST NOW, IN THIS ORDER:"
echo ""
echo " 1. Copy the recovery passphrase to your laptop (from the laptop):"
echo "      scp root@<this-server>:${RECOVERY_KEY} ~/.secrets/shadenet-vault-recovery.key"
echo "    Store a second copy offline (password manager / paper)."
echo ""
echo " 2. Verify the LAPTOP copy unlocks the vault (from the laptop):"
echo "      ssh root@<this-server> 'cryptsetup open --test-passphrase --key-file - ${VAULT_SOURCE}' \\"
echo "        < ~/.secrets/shadenet-vault-recovery.key && echo RECOVERY KEY OK"
echo "    (cryptsetup luksDump ${VAULT_SOURCE} should show 2 keyslots + a clevis token)"
echo ""
echo " 3. Remove it from the server:"
echo "      shred -u ${RECOVERY_KEY}"
echo ""
echo " 4. Once the stack is confirmed healthy, delete the plaintext copy:"
echo "      rm -rf ${OLD_DATA_DIR} && fstrim -av"
echo ""
echo " 5. Delete any the host snapshots/backups taken BEFORE today — they"
echo "    contain the unencrypted data."
echo "======================================================================"
