"""Operator control plane: auth, audit, logs, metrics, settings, and the
operator-only workflows (account recovery, venue succession, 21+ overrides).

Everything here is reached through /api/ops/* (see routes.py) and the console
at /ops/. State lives under SHADENET_OPS_DIR (default shadenet/data/ops/),
which should be mode 0700 and excluded from any public sync.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "ops"
_io_lock = threading.Lock()


def ops_dir() -> Path:
    d = Path(os.environ.get("SHADENET_OPS_DIR") or _DEFAULT_DIR)
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(name: str, default: Any) -> Any:
    path = ops_dir() / name
    with _io_lock:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return default
        except ValueError as exc:
            # A corrupt state file must not silently reset operator data.
            raise RuntimeError(f"ops state file {path} is not valid JSON: {exc}") from exc


def write_json(name: str, data: Any) -> None:
    """Atomic write with 0600 permissions."""
    path = ops_dir() / name
    tmp = path.with_suffix(path.suffix + ".tmp")
    with _io_lock:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True, default=str)
        os.replace(tmp, path)
