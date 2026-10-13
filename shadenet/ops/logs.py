"""Read structured logs back for the operator console.

Sources, in order:
  1. SHADENET_LOG_FILE (+ rotated .1 .. .N): JSON lines written by shadenet.logging.
  2. journald, for the systemd unit (journalctl -u <unit> -o json). Covers
     plain-text stderr too (tracebacks, HTTP access lines).
On the VPS container, set SHADENET_LOG_FILE to a mounted volume path.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterator

from shadenet.logging import LOG_KEEP, default_log_file

MAX_SCAN_BYTES = 8 * 1024 * 1024
LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]
JOURNAL_UNIT = os.environ.get("SHADENET_JOURNAL_UNIT", "nightcal")


def _reverse_lines(path: Path, budget: int) -> Iterator[str]:
    """Yield lines newest-first, reading at most `budget` bytes from the end."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        start = max(0, size - budget)
        f.seek(start)
        chunk = f.read()
    lines = chunk.splitlines()
    if start > 0 and lines:
        lines = lines[1:]  # first line is probably cut in half
    for raw in reversed(lines):
        yield raw.decode("utf-8", "replace")


def _file_records() -> Iterator[dict]:
    base = default_log_file()
    if not base:
        return
    budget = MAX_SCAN_BYTES
    for path in [base] + [base.with_name(f"{base.name}.{i}") for i in range(1, LOG_KEEP + 1)]:
        if budget <= 0 or not path.exists():
            continue
        size = path.stat().st_size
        for line in _reverse_lines(path, budget):
            try:
                rec = json.loads(line)
            except ValueError:
                rec = {"level": "INFO", "event": "raw", "message": line}
            yield rec
        budget -= size


def _journal_records(limit: int) -> Iterator[dict]:
    exe = shutil.which("journalctl")
    if not exe:
        return
    try:
        out = subprocess.run(
            [exe, "-u", JOURNAL_UNIT, "-o", "json", "-n", str(min(limit * 4, 5000)), "--no-pager", "-r"],
            capture_output=True, text=True, timeout=5, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return
    prio = {0: "ERROR", 1: "ERROR", 2: "ERROR", 3: "ERROR", 4: "WARNING", 5: "INFO", 6: "INFO", 7: "DEBUG"}
    for line in out.splitlines():
        try:
            j = json.loads(line)
        except ValueError:
            continue
        msg = j.get("MESSAGE", "")
        if isinstance(msg, list):  # journald encodes non-UTF8 as byte arrays
            msg = bytes(msg).decode("utf-8", "replace")
        try:
            rec = json.loads(msg)
            if not isinstance(rec, dict):
                raise ValueError
        except ValueError:
            level = prio.get(int(j.get("PRIORITY", 6)), "INFO")
            if "Traceback" in msg or " 500 " in msg:
                level = "ERROR"
            rec = {"level": level, "event": "stderr", "message": msg, "service": JOURNAL_UNIT}
        rec.setdefault("timestamp", _usec_to_iso(j.get("__REALTIME_TIMESTAMP")))
        yield rec


def _usec_to_iso(usec: Any) -> str:
    from datetime import datetime, timezone
    try:
        return datetime.fromtimestamp(int(usec) / 1e6, timezone.utc).isoformat()
    except (TypeError, ValueError):
        return ""


def source() -> dict:
    f = default_log_file()
    if f:
        return {"kind": "file", "path": str(f), "exists": f.exists()}
    if shutil.which("journalctl"):
        return {"kind": "journald", "unit": JOURNAL_UNIT}
    return {"kind": "none", "hint": "set SHADENET_LOG_FILE so the console can read logs"}


def query(*, level: str = "", service: str = "", q: str = "", trace_id: str = "", limit: int = 200) -> dict:
    min_level = LEVELS.index(level.upper()) if level.upper() in LEVELS else 0
    q = q.lower()
    src = source()
    records = _file_records() if src["kind"] == "file" else _journal_records(limit)
    out: list[dict] = []
    for rec in records:
        lvl = str(rec.get("level", "INFO")).upper()
        if lvl in LEVELS and LEVELS.index(lvl) < min_level:
            continue
        if service and rec.get("service") != service:
            continue
        if trace_id and rec.get("trace_id") != trace_id:
            continue
        if q and q not in json.dumps(rec, default=str).lower():
            continue
        out.append(rec)
        if len(out) >= limit:
            break
    return {"source": src, "count": len(out), "records": out}


def error_groups(limit: int = 500) -> list[dict]:
    """Collapse recent ERRORs by event name so repeats read as one row with a count."""
    groups: dict[str, dict] = {}
    for rec in query(level="ERROR", limit=limit)["records"]:
        key = f"{rec.get('service', '?')}:{rec.get('event', '?')}"
        g = groups.setdefault(key, {"key": key, "count": 0, "last": rec, "first_seen": rec.get("timestamp")})
        g["count"] += 1
        g["first_seen"] = rec.get("timestamp")  # newest-first, so the last one we see is the oldest
    return sorted(groups.values(), key=lambda g: g["last"].get("timestamp", ""), reverse=True)
