"""Structured JSON event logging for ShadeNet & NightCal services.

Specification per Task 6.1:
  - Every service logs structured JSON events.
  - End-to-end request tracing via trace_id / correlation_id.
  - Traceable failures: failed requests can be diagnosed end-to-end from logs alone.
  - Retention policy and operator querying documented.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_local = threading.local()

# File sink for the operator log viewer. Off unless SHADENET_LOG_FILE is set
# (the systemd unit / compose file sets it); stderr/journald always gets a copy.
LOG_ROTATE_BYTES = int(os.environ.get("SHADENET_LOG_ROTATE_MB", "20")) * 1024 * 1024
LOG_KEEP = int(os.environ.get("SHADENET_LOG_KEEP", "5"))
_file_lock = threading.Lock()


def default_log_file() -> Optional[Path]:
    raw = os.environ.get("SHADENET_LOG_FILE", "").strip()
    return Path(raw) if raw else None


def _append_rotating(path: Path, line: str) -> None:
    with _file_lock:
        try:
            if path.exists() and path.stat().st_size >= LOG_ROTATE_BYTES:
                for i in range(LOG_KEEP - 1, 0, -1):
                    older = path.with_name(f"{path.name}.{i}")
                    if older.exists():
                        older.replace(path.with_name(f"{path.name}.{i + 1}"))
                path.replace(path.with_name(f"{path.name}.1"))
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

def current_trace_id() -> str:
    """Get the current thread's active trace ID or empty string."""
    return getattr(_local, "trace_id", "")

def set_trace_id(trace_id: Optional[str] = None) -> str:
    """Set or generate a new trace ID for the current context."""
    tid = trace_id or uuid.uuid4().hex[:16]
    _local.trace_id = tid
    return tid

def clear_trace_id() -> None:
    _local.trace_id = ""


class StructuredLogger:
    def __init__(self, service: str = "nightcal", sink: Any = None, log_file: Optional[Path] = None):
        self.service = service
        self.sink = sink or sys.stderr
        self.log_file = log_file or default_log_file()

    def _emit(self, level: str, event: str, **kwargs: Any) -> dict:
        ts = datetime.now(timezone.utc).isoformat()
        trace_id = kwargs.pop("trace_id", None) or current_trace_id() or uuid.uuid4().hex[:16]
        
        record = {
            "timestamp": ts,
            "level": level.upper(),
            "service": self.service,
            "trace_id": trace_id,
            "event": event,
            **kwargs,
        }
        
        line = json.dumps(record, default=str)
        try:
            self.sink.write(line + "\n")
            self.sink.flush()
        except Exception:
            pass

        if self.log_file:
            _append_rotating(Path(self.log_file), line)
                
        return record

    def info(self, event: str, **kwargs: Any) -> dict:
        return self._emit("INFO", event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> dict:
        return self._emit("WARNING", event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> dict:
        return self._emit("ERROR", event, **kwargs)

    def debug(self, event: str, **kwargs: Any) -> dict:
        return self._emit("DEBUG", event, **kwargs)


# Global default logger
logger = StructuredLogger(service="nightcal")

def get_logger(service: str = "nightcal") -> StructuredLogger:
    """Return a StructuredLogger for the specified service name."""
    return StructuredLogger(service=service)
