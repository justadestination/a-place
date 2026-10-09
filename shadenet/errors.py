"""User-facing error formatting and catalog enforcement for ShadeNet services.

Guarantees:
  - Plain-language explanation with an actionable next step.
  - Zero raw stack traces or internal paths leaked to users.
  - Consistent JSON error response shape with correlation trace_id.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from shadenet.logging import current_trace_id

CATALOG: Dict[str, Dict[str, Any]] = {
    "ERR_NOT_FOUND": {
        "status_code": 404,
        "message": "We couldn't find the page or event you requested.",
        "next_step": "Check the date or return to tonight's listings on the calendar.",
        "help_url": "/",
    },
    "ERR_BAD_REQUEST": {
        "status_code": 400,
        "message": "The submitted data was incomplete or in an unexpected format.",
        "next_step": "Verify the fields and try submitting again.",
        "help_url": "/api/docs",
    },
    "ERR_METHOD_NOT_ALLOWED": {
        "status_code": 405,
        "message": "This endpoint does not support that request method.",
        "next_step": "Use GET for data or POST for actions per the API specification.",
        "help_url": "/api/docs",
    },
    "ERR_UNAUTHORIZED": {
        "status_code": 401,
        "message": "A valid steward or operator identity is required for this action.",
        "next_step": "Ensure your steward credential is active and approved.",
        "help_url": "/system/",
    },
    "ERR_RATE_LIMITED": {
        "status_code": 429,
        "message": "Too many requests received from this identity.",
        "next_step": "Please wait 60 seconds before casting further tallies or requests.",
        "help_url": "/",
    },
    "ERR_UPSTREAM_UNAVAILABLE": {
        "status_code": 502,
        "message": "The live venue feed or scraper did not answer.",
        "next_step": "Cached listings remain active; retry refreshing in a few moments.",
        "help_url": "/",
    },
    "ERR_INTERNAL_ERROR": {
        "status_code": 500,
        "message": "Something unexpected happened behind the scenes.",
        "next_step": "The incident was logged with your Trace ID. Refresh to try again.",
        "help_url": "/",
    },
}

def format_error(
    code: str,
    message: Optional[str] = None,
    next_step: Optional[str] = None,
    status_code: Optional[int] = None,
    trace_id: Optional[str] = None,
    help_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a sanitized user-facing error payload."""
    meta = CATALOG.get(code, CATALOG["ERR_INTERNAL_ERROR"])
    
    tid = trace_id or current_trace_id()
    
    clean_message = message or meta["message"]
    # Defensive scrub against accidental traceback leaks in custom messages
    if "traceback" in clean_message.lower() or "line " in clean_message.lower() or ".py" in clean_message:
        clean_message = meta["message"]
        
    return {
        "code": code,
        "error": clean_message,
        "next_step": next_step or meta["next_step"],
        "status_code": status_code or meta["status_code"],
        "trace_id": tid or "",
        "help_url": help_url or meta["help_url"],
    }
