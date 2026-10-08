"""towncrier - continuous local event discovery (shadenet.towncrier).

Legacy facade. Canonical code lives under shadenet/towncrier/; this module is a
thin re-export shim so existing tests and integrations that import
towncrier.store, towncrier.discover, towncrier.entities, towncrier.normalize,
towncrier.resolve, towncrier.facts, towncrier.zine_task_done still work, while
the canonical package is used without out-of-tree (Docker-hostile) symlinks.
"""
import os
import sys
from pathlib import Path

# repo root: `towncrier` is a top-level directory, so its parent is the repo root.
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import shadenet.towncrier as _shadenet_towncrier  # noqa: E402

# Re-export the whole canonical towncrier package as this package's namespace.
__all__ = [
    "discover", "entities", "facts", "normalize", "resolve", "store",
    "zine_task_done",
]
for _attr in [
    "discover", "entities", "facts", "normalize", "resolve", "store",
    "zine_task_done",
]:
    try:
        _val = getattr(_shadenet_towncrier, _attr)
    except AttributeError:
        _val = _shadenet_towncrier
    locals()[_attr] = _val
    globals()[_attr] = _val

__version__ = "0.1.0"
