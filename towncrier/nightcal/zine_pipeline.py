"""Zine content modules pipeline (shadenet.horizon.zine_pipeline).

Legacy facade. Canonical implementation lives in shadenet/horizon/zine_pipeline.py;
this module forwards to the canonical package.
"""
import os
import sys
from pathlib import Path

# zine_pipeline.py is at towncrier/nightcal/zine_pipeline.py, three levels up = repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import shadenet.horizon.zine_pipeline as _canon  # noqa: E402

for _attr in dir(_canon):
    if _attr.startswith('_'):
        continue
    locals()[_attr] = getattr(_canon, _attr)
    globals()[_attr] = getattr(_canon, _attr)
