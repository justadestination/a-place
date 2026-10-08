"""Legacy facade for nightcal.fill.

Canonical implementation lives in shadenet/nightcal/fill.py; this module
forwards everything to it, including private names tests import.
"""
import os
import sys
from pathlib import Path

# fill.py is at towncrier/nightcal/fill.py, so three levels up reaches the
# repo root: fill.py -> nightcal -> towncrier -> repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import shadenet.nightcal.fill as _canon  # noqa: E402

# Forward every public AND private name so tests importing private names work.
for _attr in dir(_canon):
    if _attr.startswith('__'):
        continue
    locals()[_attr] = getattr(_canon, _attr)
    globals()[_attr] = getattr(_canon, _attr)
