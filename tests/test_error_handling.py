"""Integration test suite for Task 6.2: Error handling.

Asserts:
  - User-facing errors are plain-language with a next step.
  - Zero raw stack traces or internal filenames leaked.
  - Error catalog consistency.
  - 404/500 design system pages exist with proper recovery links.
"""

from pathlib import Path
import pytest
from shadenet.errors import CATALOG, format_error
from shadenet.logging import set_trace_id, clear_trace_id

def test_error_catalog_completeness():
    required_keys = {"status_code", "message", "next_step", "help_url"}
    for code, meta in CATALOG.items():
        assert required_keys.issubset(meta.keys()), f"Catalog entry {code} missing required keys"
        assert meta["status_code"] in {400, 401, 404, 405, 429, 500, 502}
        assert meta["message"]
        assert meta["next_step"]
        # Invariant: No technical jargon or code traces in catalog messages
        assert "traceback" not in meta["message"].lower()
        assert "exception" not in meta["message"].lower()

def test_format_error_structure():
    set_trace_id("trace-err-test-42")
    err = format_error("ERR_NOT_FOUND")
    
    assert err["code"] == "ERR_NOT_FOUND"
    assert err["status_code"] == 404
    assert err["error"] == "We couldn't find the page or event you requested."
    assert err["next_step"] == "Check the date or return to tonight's listings on the calendar."
    assert err["trace_id"] == "trace-err-test-42"
    assert err["help_url"] == "/"
    clear_trace_id()

def test_format_error_stack_trace_scrubbing():
    """Security invariant: Nothing leaks stack traces."""
    leaky_message = "Traceback (most recent call last):\n  File '/app/db.py', line 45, in query\nDatabaseError: failed"
    err = format_error("ERR_INTERNAL_ERROR", message=leaky_message)
    
    assert "Traceback" not in err["error"]
    assert ".py" not in err["error"]
    assert err["error"] == "Something unexpected happened behind the scenes."
    assert err["next_step"] == "The incident was logged with your Trace ID. Refresh to try again."

def test_static_error_pages_exist():
    root = Path(__file__).resolve().parent.parent
    page_404 = root / "web" / "404.html"
    page_500 = root / "web" / "500.html"
    
    assert page_404.exists(), "web/404.html does not exist"
    assert page_500.exists(), "web/500.html does not exist"
    
    html_404 = page_404.read_text(encoding="utf-8")
    assert "404" in html_404
    assert "Return to Calendar" in html_404
    assert "Traceback" not in html_404
    
    html_500 = page_500.read_text(encoding="utf-8")
    assert "500" in html_500
    assert "Return to Calendar" in html_500
    assert "Traceback" not in html_500
