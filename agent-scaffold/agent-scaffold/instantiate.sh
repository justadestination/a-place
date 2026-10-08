#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "== Agent scaffold instantiate =="

# 1. State dir
mkdir -p state
if [[ ! -f state/tasks.json ]]; then
  python3 -c "
import yaml, json, pathlib
seed = yaml.safe_load(open('config/tasks.yaml'))['seed']
pathlib.Path('state/tasks.json').write_text(json.dumps(seed, indent=2))
print('Seeded state/tasks.json')
"
fi

# 2. Python deps for MCP
if [[ -f mcp-server/requirements.txt ]]; then
  pip3 install -q -r mcp-server/requirements.txt || echo "(pip install failed — install manually)"
fi

# 3. Quick config check
echo ""
echo "Edit these before first real run:"
echo "  config/matrix.yaml   → homeserver, room_id, user_id"
echo "  config/agent.yaml    → local model name / endpoint"
echo ""
echo "Then:"
echo "  cd mcp-server && python3 server.py          # skeleton smoke test"
echo "  # or wire the handlers into a real MCP SDK server"
echo ""
echo "Lexicon, tasks, roles, and inference policy are ready."
echo "Done."