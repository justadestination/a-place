# Shadenet build plan — Verifiable baseline & layout decisions
# ===============================================
#  PROVENANCE (verified just now, not assumed):
#   towncrier/test_discover.py        -> 182 passed
#   towncrier/test_entities.py        -> 43 passed
#   towncrier/test_nightcal.py        -> 122 passed
#   towncrier/test_normalize.py       -> 59 passed
#   towncrier/test_resolve.py         -> 45 passed
#   towncrier/test_social_hardened.py -> 16 passed
#   total towncrier = 467  (matches TODO.md claim)
#   Python 3.14.7 at /usr/bin/python3; pytest 9.1.1
#   httpx 0.28.1, PyYAML, frontmatter 3.0.8, jsonschema 4.26.0, mcp 2.2.0, aiohttp 3.14.3
#   sqlite 3.53.4
#   Cross-imports observed (import survey):
#     nightcal.*  -> towncrier.* (normalize, resolve, store, entities, discover, facts)
#                   -> nightcal.* (internal siblings)
#     towncrier.towncrier  -> rapildfuzz, requests, sqlite3, itself
#     agent-scaffold.*    -> command_engine, personal_agent, venue_agent,
#                           public_board, subscriptions, inboxes, mcp-server.server,
#                           mcp-server.logstack
#   No existing `shadenet/` package. No Dockerfile / docker-compose.
#   zine/vault has 3 markdown pieces; zine/avr_graph.json, edges/edges.json, nodes/nodes.json exist.
#   tests/ run as plain `python3 tests/X.py` (sys.path insert to repo root).
#   data/shadenet.db MUST NOT be deleted.

#  LAYOUT DECISIONS
#   - shadenet/nightcal  <- canonical shadenet.nightcal (contents = towncrier/nightcal)
#   - shadenet/horizon   <- canonical shadenet.horizon (zine compiler + vault)
#   - shadenet/serendipilyst <- shadenet.serendipilyst (marketplace & boards)
#   - shadenet/steward   <- shadenet.steward (agent backend + A2A protocol)
#   - shadenet/towncrier <- SYMLINK to existing towncrier/  (preserves towncrier.* imports)
#   - shadenet/agent-scaffold <- SYMLINK to existing agent-scaffold/ (preserves scaffold imports)
#   - shadenet/compat/ <- backward-compat shim for bare `import towncrier`, `import nightcal`,
#                        `import zine`, `import agent_scaffold` so EXISTING tests keep passing.
#   - shadenet/discover.py        dynamic geographic bootstrap (SHADENET_LAT/LON/RADIUS_KM)
#   - shadenet/sync_mesh.py       tri-sync mesh (SQLite changefeeds + zine git commits)
#   - shadenet/Dockerfile
#   - shadenet/docker-compose.yml
#   - shadenet/tests/test_shadenet_acceptance.py

#  STEP 1: create shadenet package dirs
#  STEP 2: move nightcal/* into shadenet/nightcal; move zine pipeline + vault into shadenet/horizon
#  STEP 3: write shadenet/compat (__init__.py + modules that re-export old names)
#  STEP 4: write shadenet/__init__.py + package-level __init__.py for shadenet.nightcal
#  STEP 5: verify existing 467 tests still pass (via compat shim)
#  STEP 6: add future work + verification log

#  TODO: after tests pass, remove shadenet/compat when all code migrated to shadenet.*
