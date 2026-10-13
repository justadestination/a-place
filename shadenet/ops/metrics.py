"""In-process request metrics: counts, status classes, latency, per-minute series.

Cheap enough to run on every request. Resets on restart; for history, ship the
http_request log events somewhere durable.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

_lock = threading.Lock()
_started = time.time()
_WINDOW_MINUTES = 60

_by_route: dict[str, dict] = defaultdict(lambda: {"count": 0, "errors": 0, "total_ms": 0.0, "max_ms": 0.0})
_status: dict[str, int] = defaultdict(int)
_minutes: deque = deque(maxlen=_WINDOW_MINUTES)  # (minute_epoch, count, errors)
_latencies: deque = deque(maxlen=2000)


def route_group(path: str) -> str:
    """Collapse ids so /api/events/abc and /api/events/def count together."""
    path = path.split("?", 1)[0]
    if path.startswith("/api/"):
        # /api/<area>[/<action>]: keep a readable action, drop ids ("evt_123", hex, numbers)
        parts = path.split("/")[1:4]
        if len(parts) == 3 and (any(ch.isdigit() for ch in parts[2]) or len(parts[2]) > 24):
            parts = parts[:2]
        return "/" + "/".join(p for p in parts if p)
    if path.startswith(("/day/", "/embed/")):
        return "/" + path.split("/")[1] + "/*"
    if "." in path.rsplit("/", 1)[-1]:
        return "static"
    return "page"


def record(method: str, path: str, status: int, ms: float) -> None:
    key = f"{method} {route_group(path)}"
    minute = int(time.time() // 60)
    is_err = status >= 500
    with _lock:
        r = _by_route[key]
        r["count"] += 1
        r["errors"] += int(is_err)
        r["total_ms"] += ms
        r["max_ms"] = max(r["max_ms"], ms)
        _status[f"{status // 100}xx"] += 1
        _latencies.append(ms)
        if _minutes and _minutes[-1][0] == minute:
            m, c, e = _minutes[-1]
            _minutes[-1] = (m, c + 1, e + int(is_err))
        else:
            _minutes.append((minute, 1, int(is_err)))


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return round(values[min(len(values) - 1, int(len(values) * p))], 1)


def snapshot() -> dict:
    with _lock:
        lat = list(_latencies)
        routes = [
            {"route": k, "count": v["count"], "errors": v["errors"],
             "avg_ms": round(v["total_ms"] / v["count"], 1) if v["count"] else 0, "max_ms": round(v["max_ms"], 1)}
            for k, v in _by_route.items()
        ]
        return {
            "uptime_seconds": round(time.time() - _started),
            "status": dict(_status),
            "latency_ms": {"p50": _pct(lat, 0.5), "p95": _pct(lat, 0.95), "p99": _pct(lat, 0.99)},
            "per_minute": [{"minute": m * 60, "count": c, "errors": e} for m, c, e in _minutes],
            "routes": sorted(routes, key=lambda r: r["count"], reverse=True),
        }
