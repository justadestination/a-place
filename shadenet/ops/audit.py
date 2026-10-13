"""Append-only, hash-chained audit trail of every operator action.

Each line carries the SHA-256 of the previous line, so deleting or editing an
entry breaks verify(). It's tamper-evident, not tamper-proof: ship the file
off-box (06_backup_sync.sh) if you need the latter.
"""

from __future__ import annotations

import hashlib
import json
import threading
from typing import Any

from shadenet.ops import now_iso, ops_dir

_lock = threading.Lock()
_FILE = "audit.jsonl"
_GENESIS = "0" * 64


def _last_hash() -> str:
    path = ops_dir() / _FILE
    if not path.exists():
        return _GENESIS
    last = ""
    with open(path, "rb") as f:
        for line in f:
            if line.strip():
                last = line
    return hashlib.sha256(last.strip()).hexdigest() if last else _GENESIS


def record(actor: str, action: str, *, target: str = "", ip: str = "", ok: bool = True, **detail: Any) -> dict:
    with _lock:
        entry = {
            "ts": now_iso(),
            "actor": actor,
            "action": action,
            "target": target,
            "ip": ip,
            "ok": ok,
            "detail": detail,
            "prev": _last_hash(),
        }
        line = json.dumps(entry, sort_keys=True, default=str)
        with open(ops_dir() / _FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return entry


def tail(limit: int = 200, actor: str = "", action: str = "") -> list[dict]:
    path = ops_dir() / _FILE
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if actor and e.get("actor") != actor:
            continue
        if action and not str(e.get("action", "")).startswith(action):
            continue
        out.append(e)
    return out[-limit:][::-1]


def verify() -> dict:
    """Walk the chain; report the first broken link, if any."""
    path = ops_dir() / _FILE
    if not path.exists():
        return {"ok": True, "entries": 0}
    prev = _GENESIS
    n = 0
    for n, raw in enumerate(path.read_bytes().splitlines(), start=1):
        if not raw.strip():
            continue
        if json.loads(raw).get("prev") != prev:
            return {"ok": False, "entries": n, "broken_at_line": n}
        prev = hashlib.sha256(raw.strip()).hexdigest()
    return {"ok": True, "entries": n}
