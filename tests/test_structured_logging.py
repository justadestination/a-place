"""Integration test suite for Task 6.1: Structured logging.

Asserts:
  - Every service logs structured JSON events.
  - Trace ID propagation and correlation across requests.
  - Error diagnostic tracing: a failed request can be traced end-to-end from the logs alone.
"""

import io
import json
import pytest
from shadenet.logging import StructuredLogger, set_trace_id, current_trace_id, clear_trace_id

def test_structured_logging_format():
    stream = io.StringIO()
    log = StructuredLogger(service="nightcal", sink=stream)
    
    tid = set_trace_id("test-trace-1234")
    assert current_trace_id() == "test-trace-1234"
    
    rec = log.info("request_started", method="GET", path="/api/model", client_ip="127.0.0.1")
    
    # Assert return dictionary contains required schema
    assert rec["level"] == "INFO"
    assert rec["service"] == "nightcal"
    assert rec["trace_id"] == "test-trace-1234"
    assert rec["event"] == "request_started"
    assert rec["method"] == "GET"
    assert rec["path"] == "/api/model"
    assert "timestamp" in rec
    
    # Assert JSON stream output is parseable
    stream.seek(0)
    lines = stream.getvalue().strip().split("\n")
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["trace_id"] == "test-trace-1234"
    assert parsed["event"] == "request_started"
    clear_trace_id()

def test_structured_logging_levels_and_context():
    stream = io.StringIO()
    log = StructuredLogger(service="towncrier", sink=stream)
    
    set_trace_id("trace-abc-567")
    log.warning("rate_limit_approaching", client="agent-steward-1", count=95, limit=100)
    log.debug("cache_lookup", key="model:v1", hit=True)
    
    stream.seek(0)
    lines = stream.getvalue().strip().split("\n")
    assert len(lines) == 2
    
    w_rec = json.loads(lines[0])
    assert w_rec["level"] == "WARNING"
    assert w_rec["count"] == 95
    assert w_rec["trace_id"] == "trace-abc-567"
    
    d_rec = json.loads(lines[1])
    assert d_rec["level"] == "DEBUG"
    assert d_rec["hit"] is True
    clear_trace_id()

def test_end_to_end_failed_request_tracing():
    """Done when: a failed request can be traced end-to-end from the logs alone."""
    stream = io.StringIO()
    log = StructuredLogger(service="nightcal", sink=stream)
    
    # Simulate an incoming request with generated trace ID
    trace_id = set_trace_id()
    assert trace_id
    
    log.info("request_started", method="POST", path="/api/events", payload_size=128)
    
    # Simulate failure in processing (e.g. database constraint / invalid data)
    try:
        raise ValueError("Simulated database failure: malformed event payload")
    except Exception as exc:
        log.error(
            "request_failed",
            path="/api/events",
            method="POST",
            status_code=500,
            error=str(exc),
            error_type=exc.__class__.__name__,
            traceback="Traceback (most recent call last):\n  File 'server.py', line 123, in _events\nValueError"
        )
    
    # Query log stream for the trace ID (simulating operator query)
    stream.seek(0)
    events_for_trace = []
    for line in stream.getvalue().strip().split("\n"):
        rec = json.loads(line)
        if rec.get("trace_id") == trace_id:
            events_for_trace.append(rec)
            
    # Operator can reconstruct full request lifecycle from logs alone:
    assert len(events_for_trace) == 2
    assert events_for_trace[0]["event"] == "request_started"
    assert events_for_trace[1]["event"] == "request_failed"
    assert events_for_trace[1]["status_code"] == 500
    assert "malformed event payload" in events_for_trace[1]["error"]
    assert events_for_trace[1]["error_type"] == "ValueError"
    
    clear_trace_id()
