"""A2UI night calendar fed by the towncrier store (shadenet.nightcal).

Legacy facade. Canonical implementation lives in shadenet/nightcal/; this module
forwards its public names to the canonical package.
"""
import os
import sys
from pathlib import Path

# __init__.py is at towncrier/nightcal/__init__.py, so three levels up = repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import shadenet.nightcal as _canon  # noqa: E402

for _attr in dir(_canon):
    if _attr.startswith('_'):
        continue
    locals()[_attr] = getattr(_canon, _attr)
    globals()[_attr] = getattr(_canon, _attr)
