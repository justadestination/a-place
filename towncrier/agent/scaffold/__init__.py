"""Derivee agent scaffold (shadenet.steward).

Legacy facade. Canonical code lives under shadenet/steward/; this module is a
thin re-export shim so existing tests and integrations that import the
agent-scaffold package continue to work, while the canonical package is used
without out-of-tree symlinks.
"""
import os
import sys
from pathlib import Path

# Self-bootstrap: make the repo root importable so `shadenet` is on sys.path.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import shadenet.steward as _shadenet_steward  # noqa: E402

__all__ = [
    "server", "command_engine", "inboxes", "personal_agent", "venue_agent",
    "public_board", "subscriptions", "agent_scaffold",
]
for _attr in [
    "server", "command_engine", "inboxes", "personal_agent", "venue_agent",
    "public_board", "subscriptions", "agent_scaffold",
]:
    try:
        _val = getattr(_shadenet_steward, _attr)
    except AttributeError:
        _val = _shadenet_steward
    locals()[_attr] = _val
    globals()[_attr] = _val
