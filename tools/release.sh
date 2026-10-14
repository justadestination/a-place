#!/usr/bin/env bash
# Build releases/<sha>.tar.gz from a commit. Only tracked files ship; live
# data, state and secrets never do (they stay on the server, see
# deploy/install_release.sh).
set -euo pipefail
commit="${1:-HEAD}"
sha="$(git rev-parse --short=12 "$commit")"
mkdir -p releases
git archive --format=tar.gz --prefix="$sha/" -o "releases/$sha.tar.gz" "$commit" \
  -- . ':!shadenet/data' ':!state' ':!backups' ':!docs/audit/report.json'
echo "releases/$sha.tar.gz"
