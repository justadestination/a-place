"""Legacy facade for the towncrier package (shadenet.facts).

Canonical implementation lives in shadenet.towncrier.facts; this facade forwards to it so
existing tests that `import towncrier.store`, `from towncrier.entities
import ...` still resolve without out-of-tree symlinks.
"""
import os
import sys
from pathlib import Path

# repo root: towncrier/ is a top-level directory, so its parent is the repo root.
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import shadenet.towncrier.facts as _canon  # noqa: E402

# Re-export every name (public + private) so `import towncrier.store` and
# `from towncrier.store import X` all work.
for _attr in dir(_canon):
    if _attr.startswith('__'):
        continue
    globals()[_attr] = getattr(_canon, _attr)
