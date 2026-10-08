"""Umwelt Horizon zine compiler & vault (shadenet.horizon).

Legacy facade. Canonical code lives under shadenet/horizon/; this module is a
thin re-export shim so existing tests and integrations that import zine
continue to work, while the canonical package is used without out-of-tree
symlinks.
"""
import os
import sys
from pathlib import Path

# Self-bootstrap: make the repo root importable so `shadenet` is on sys.path.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import shadenet.horizon as _shadenet_horizon  # noqa: E402

__all__ = [
    "zine_pipeline", "AVR_GRAPH", "NODES_FILE", "EDGES_FILE", "VAULT_DIR",
]
for _attr in [
    "zine_pipeline", "AVR_GRAPH", "NODES_FILE", "EDGES_FILE", "VAULT_DIR",
]:
    try:
        _val = getattr(_shadenet_horizon, _attr)
    except AttributeError:
        _val = _shadenet_horizon
    locals()[_attr] = _val
    globals()[_attr] = _val
