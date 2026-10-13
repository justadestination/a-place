#!/usr/bin/env bash
# ==============================================================================
# backup_host.sh — Append-only borg target for ShadeNet production
# Run ON BACKUP-HOST (backup-host) as root, NOT on the production VPS:
#   PROD_PUBKEY='ssh-ed25519 AAAA... shadenet-backup@...' bash backup_host.sh
#
# The production key can ONLY run `borg serve --append-only` inside
# /srv/borg — no shell, no forwarding, no deleting history.
# Space is reclaimed by a local monthly `borg compact` (needs no passphrase).
# ==============================================================================
set -euo pipefail

PROD_PUBKEY="${PROD_PUBKEY:?Set PROD_PUBKEY to the key printed by 06_backup_sync.sh}"
BACKUP_USER="shadenet-backup"
BORG_BASE="/srv/borg"
REPO="${BORG_BASE}/shadenet"

case "${PROD_PUBKEY}" in
  ssh-ed25519\ *) ;;
  *) echo "PROD_PUBKEY does not look like an ed25519 public key." >&2; exit 1 ;;
esac

echo "===> [1/3] Installing borg and creating restricted backup user..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq borgbackup

if ! id "${BACKUP_USER}" &>/dev/null; then
  # Needs a real shell: sshd runs the forced command through it
  useradd --system --create-home --home-dir "${BORG_BASE}" --shell /bin/sh "${BACKUP_USER}"
fi
install -d -m 700 -o "${BACKUP_USER}" -g "${BACKUP_USER}" "${BORG_BASE}" "${BORG_BASE}/.ssh"

echo "===> [2/3] Locking production key to append-only borg serve..."
cat > "${BORG_BASE}/.ssh/authorized_keys" <<EOF
command="borg serve --append-only --restrict-to-path ${BORG_BASE}",restrict ${PROD_PUBKEY}
EOF
chown "${BACKUP_USER}:${BACKUP_USER}" "${BORG_BASE}/.ssh/authorized_keys"
chmod 600 "${BORG_BASE}/.ssh/authorized_keys"

echo "===> [3/3] Installing monthly compaction timer..."
cat > /etc/systemd/system/shadenet-borg-compact.service <<EOF
[Unit]
Description=Reclaim space in ShadeNet borg repo (finalises pruned archives)
ConditionPathExists=${REPO}/config

[Service]
Type=oneshot
User=${BACKUP_USER}
ExecStart=/usr/bin/borg compact ${REPO}
Nice=10
IOSchedulingClass=idle
EOF

cat > /etc/systemd/system/shadenet-borg-compact.timer <<'EOF'
[Unit]
Description=Monthly ShadeNet borg compaction

[Timer]
OnCalendar=monthly
RandomizedDelaySec=6h
Persistent=true

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now shadenet-borg-compact.timer

echo "============================================================"
echo " ✓ backup-host ready: ${BACKUP_USER}@$(hostname) -> ${REPO} (append-only)"
echo "   Free space: $(df -h "${BORG_BASE}" | awk 'NR==2 {print $4}')"
echo ""
echo " Compaction is what makes deletions permanent. If production is ever"
echo " compromised, STOP shadenet-borg-compact.timer first — every archive"
echo " an attacker 'pruned' is still recoverable until compaction runs."
echo "============================================================"
