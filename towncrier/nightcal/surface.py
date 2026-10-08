"""Legacy facade for nightcal.surface.

Canonical implementation lives in shadenet/nightcal/surface.py; this module
forwards everything to it.
"""
import os
import sys
from pathlib import Path

# surface.py is at towncrier/nightcal/surface.py, so three levels up reaches
# the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import shadenet.nightcal.surface as _canon  # noqa: E402

for _attr in dir(_canon):
    if _attr.startswith('__'):
        continue
    locals()[_attr] = getattr(_canon, _attr)
    globals()[_attr] = getattr(_canon, _attr)
