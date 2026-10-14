#!/usr/bin/env bash
# Install one release on the server, side by side, and make it live.
#
#   PUBLIC_DOMAIN=<domain> install_release.sh <sha>
#
# Expects /tmp/<sha>.tar.gz (from tools/release.sh). Layout:
#   /opt/shadenet                  -> symlink to the live release
#   /opt/shadenet-releases/<sha>/  one directory per release
#   /opt/shadenet-shared/<dir>     runtime state, linked into every release
#
# The first run turns a plain /opt/shadenet directory into this layout: its
# runtime state moves to shadenet-shared and the old tree is kept as
# releases/previous, linked to the same state, so rollback still works.
#
# After the switch the app must answer on 127.0.0.1:8765, or the previous
# release is put back and the script fails.
set -euo pipefail

sha="${1:?usage: PUBLIC_DOMAIN=<domain> install_release.sh <sha>}"
domain="${PUBLIC_DOMAIN:?set PUBLIC_DOMAIN (the real domain behind the example.org placeholders)}"
# Overridable for a local rehearsal; the defaults are the server's.
ROOT="${ROOT:-/opt/shadenet}"
RELEASES="${RELEASES:-/opt/shadenet-releases}"
SHARED="${SHARED:-/opt/shadenet-shared}"
SERVICE="${SERVICE:-shadenet}"
SYSTEMCTL="${SYSTEMCTL:-systemctl}"
OWNER="${OWNER:-www-data:www-data}"
HEALTH_BASE="${HEALTH_BASE:-http://127.0.0.1:8765}"
STATE_DIRS=(shadenet/data state zine-automation/state agent-scaffold/agent-scaffold/state shadenet/steward/state shadenet/.cache)
# Pages that carry the public hostname; the repo keeps example.org placeholders.
HOST_PAGES=(shadenet/nightcal/static/operator.html web/operator/index.html web/print/index.html)

link_state() {  # link_state <release dir>
  local dir="$1" d
  for d in "${STATE_DIRS[@]}"; do
    mkdir -p "$SHARED/$d" "$(dirname "$dir/$d")"
    rm -rf "${dir:?}/$d"
    ln -s "$SHARED/$d" "$dir/$d"
  done
}

healthy() {  # healthy <path>...
  local p
  for p in "$@"; do
    [[ "$(curl -s -o /dev/null -w '%{http_code}' "$HEALTH_BASE$p")" == 200 ]] || return 1
  done
}

switch_to() {  # switch_to <release dir> <health path>...
  local dir="$1"; shift
  ln -sfn "$dir" "$ROOT.next"
  mv -T "$ROOT.next" "$ROOT"
  chown -h "$OWNER" "$ROOT"
  $SYSTEMCTL restart "$SERVICE"
  local i
  for i in $(seq 1 20); do healthy "$@" && return 0; sleep 1; done
  return 1
}

mkdir -p "$RELEASES" "$SHARED"
new="$RELEASES/$sha"
[[ -e "$new" ]] && { echo "release $sha already unpacked at $new" >&2; exit 1; }
tar -C "$RELEASES" -xzf "/tmp/$sha.tar.gz"
for f in "${HOST_PAGES[@]}"; do
  [[ -f "$new/$f" ]] && sed -i "s/\([a-z]*\)\.example\.org/\1.$domain/g" "$new/$f"
done
link_state "$new"
chown -R "$OWNER" "$new"

if [[ -L "$ROOT" ]]; then
  previous="$(readlink -f "$ROOT")"
else
  # First run: stop writes, move state out, keep the old tree as "previous".
  $SYSTEMCTL stop "$SERVICE"
  for d in "${STATE_DIRS[@]}"; do
    if [[ -e "$ROOT/$d" && ! -L "$ROOT/$d" ]]; then
      mkdir -p "$(dirname "$SHARED/$d")"
      rm -rf "${SHARED:?}/$d"
      mv "$ROOT/$d" "$SHARED/$d"
    fi
  done
  mv "$ROOT" "$RELEASES/previous"
  link_state "$RELEASES/previous"
  chown -R "$OWNER" "$SHARED"
  previous="$RELEASES/previous"
fi

if switch_to "$new" / /road/ /api/model; then
  echo "live: $sha (previous: $(basename "$previous"))"
else
  echo "release $sha failed its health check; rolling back to $(basename "$previous")" >&2
  # The previous release may predate /road/, so it only has to serve the basics.
  switch_to "$previous" / /api/model || echo "ROLLBACK ALSO FAILED: check systemctl status $SERVICE" >&2
  exit 1
fi
