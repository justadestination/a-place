#!/usr/bin/env bash
# Public smoke checks. Exit 1 on the first wrong status.
set -euo pipefail
base="https://${SHADY_HOST:?set SHADY_HOST}"
check() { got="$(curl -s -o /dev/null -w '%{http_code}' "$base$1")"; [[ "$got" == "$2" ]] || { echo "FAIL $1 $got (want $2)"; exit 1; }; echo "ok   $1 $got"; }
check /                         200
check /road/                    200
check /road/zine-wall.js        200
check /steward/house/stamp.js   200
check /zine/                    200
check /data/zine.json           200
check /api/model                200
check /api/operator/status      404
check /api/ops/login            404
curl -s "$base/road/" | grep -q 'bust = "timeline' && echo "ok   road cache token present"
