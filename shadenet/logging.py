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
        self.log_file = log_file

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
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass
                
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
