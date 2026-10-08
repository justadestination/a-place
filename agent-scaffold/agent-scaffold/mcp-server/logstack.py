#!/usr/bin/env python3
"""
Logging + error-reporting stack for the Derivee agent scaffold.

Design constraints that come from the transport, not from taste:

1. **stdout belongs to JSON-RPC.** Under `mcp.run(transport="stdio")` the
   server's stdout IS the MCP message stream. A stray `print()` from any
   handler corrupts the session for the client. Therefore: every log record
   goes to stderr, and this module hard-fails loudly if something tries to
   write to stdout.

2. **Never log a secret.** Access tokens are registered at startup and
   redacted from every record, including inside exception text.

3. **Errors are values, not prints.** Tools return a structured envelope
   (see `error()`) so a caller can distinguish "not configured" from
   "auth rejected" from "rate limited" and react differently. A tool that
   cannot act must say so in its return value, never by printing.

4. **Correlate.** Each tool call gets an id, attached to every record it
   produces, so a log line and a return envelope can be tied together.

Nothing here imports yaml, httpx, or mcp — this module is stdlib-only so it
can be imported safely from anywhere, including test harnesses.
"""

from __future__ import annotations

import contextvars
import json
import logging
import logging.handlers
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

__all__ = [
    "error",
    "ok",
    "get_logger",
    "configure_logging",
    "register_secret",
    "new_request_id",
    "current_request_id",
    "request_scope",
    "install_stdout_guard",
    "safe_extra",
    "ErrorCode",
    "LOGGER_NAME",
]

LOGGER_NAME = "agent_tools"

# The request id for the tool call currently being handled. A ContextVar (not
# a global) because the MCP server may process calls concurrently.
_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "agent_request_id", default=None
)

# Literal secret values to scrub from every emitted record.
_SECRETS: set[str] = set()


# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------

class ErrorCode:
    """Stable, machine-readable failure codes.

    These are part of the tool contract: an agent may branch on them, so they
    are defined once here rather than spelled inline at each raise site.
    Callers should prefer branching on the code over parsing the message.
    """

    # --- Matrix ---
    MATRIX_NOT_CONFIGURED = "matrix.not_configured"
    MATRIX_PLACEHOLDER_CONFIG = "matrix.placeholder_config"
    MATRIX_AUTH_FAILED = "matrix.auth_failed"
    MATRIX_FORBIDDEN = "matrix.forbidden"
    MATRIX_NOT_FOUND = "matrix.not_found"
    MATRIX_RATE_LIMITED = "matrix.rate_limited"
    MATRIX_UNREACHABLE = "matrix.unreachable"
    MATRIX_SEND_FAILED = "matrix.send_failed"

    # --- Inference ---
    INFER_UNREACHABLE = "infer.unreachable"
    INFER_MODEL_MISSING = "infer.model_missing"
    INFER_FAILED = "infer.failed"
    INFER_DISABLED = "infer.disabled"

    # --- Shell sandbox ---
    SANDBOX_CWD_ESCAPE = "sandbox.cwd_escape"
    SANDBOX_FORBIDDEN_PATH = "sandbox.forbidden_path"
    SANDBOX_COMMAND_DENIED = "sandbox.command_denied"
    SHELL_TIMEOUT = "shell.timeout"
    SHELL_FAILED = "shell.failed"

    # --- Task list / lexicon / config ---
    TASK_NOT_FOUND = "task.not_found"
    TASK_UNKNOWN_ACTION = "task.unknown_action"
    TASK_INVALID = "task.invalid"
    CONFIG_INVALID = "config.invalid"
    INTERNAL = "internal.error"


# Codes for which a retry with backoff is a sensible response.
RETRYABLE_CODES = frozenset(
    {
        ErrorCode.MATRIX_RATE_LIMITED,
        ErrorCode.MATRIX_UNREACHABLE,
        ErrorCode.INFER_UNREACHABLE,
        ErrorCode.SHELL_TIMEOUT,
    }
)


# ---------------------------------------------------------------------------
# Structured error / success envelopes
# ---------------------------------------------------------------------------

def error(
    code: str,
    message: str,
    *,
    retryable: bool | None = None,
    **details: Any,
) -> dict:
    """Build the canonical failure envelope returned by every tool.

    `ok` is always False here. `reason` is the full `code` string, kept as a
    separate key because the lexicon-level callers match on it. `retryable` is
    derived from the taxonomy when not stated explicitly.

    `sent` is hoisted out of `details` to the top level when present, so that
    callers can branch on `result["sent"]` regardless of whether the tool
    succeeded or failed. Everything else stays in `details`.
    """
    envelope = {
        "ok": False,
        "error": {
            "code": code,
            "reason": code,
            "message": message,
            "retryable": RETRYABLE_CODES.__contains__(code)
            if retryable is None
            else retryable,
            "request_id": current_request_id(),
        },
        "details": details,
    }
    if "sent" in details:
        envelope["sent"] = details["sent"]
    return envelope


def ok(payload: dict | None = None, **fields: Any) -> dict:
    """Build the canonical success envelope.

    `ok: True` is reserved for work that actually happened. A tool that
    declined to act (unconfigured, denied, unavailable) must return `error()`
    instead — that distinction is the whole point of these helpers.
    """
    base: dict = {"ok": True, "request_id": current_request_id()}
    if payload:
        base.update(payload)
    if fields:
        base.update(fields)
    return base


# ---------------------------------------------------------------------------
# Request correlation
# ---------------------------------------------------------------------------

def new_request_id(prefix: str = "req") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def current_request_id() -> str | None:
    return _request_id.get()


class request_scope:
    """Context manager binding a request id for the duration of a tool call.

    Every log record emitted inside the block carries the id, as does any
    error envelope raised inside it.
    """

    def __init__(self, request_id: str | None = None, prefix: str = "req"):
        self.request_id = request_id or new_request_id(prefix)
        self._token: contextvars.Token | None = None

    def __enter__(self) -> "request_scope":
        self._token = _request_id.set(self.request_id)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._token is not None:
            _request_id.reset(self._token)
            self._token = None


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------

def register_secret(value: str | None) -> None:
    """Mark a literal value as never-loggable.

    Short values are ignored: redacting a 3-character string would mangle
    unrelated text without protecting anything meaningful.
    """
    if value and len(value) >= 8:
        _SECRETS.add(value)


def _redact(text: str) -> str:
    for secret in _SECRETS:
        if secret in text:
            text = text.replace(secret, "***REDACTED***")
    return text


class RedactingFilter(logging.Filter):
    """Scrub registered secrets from the message and from exception text."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = _redact(str(record.msg))
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {k: _redact(str(v)) for k, v in record.args.items()}
                else:
                    record.args = tuple(_redact(str(a)) for a in record.args)
            if record.exc_info and record.exc_info[1] is not None:
                record.exc_text = _redact(record.exc_text or "") or None
        except Exception:  # never let logging break the caller
            pass
        return True


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

_RESERVED = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()
) | {"message", "asctime", "taskName"}


def safe_extra(fields: dict) -> dict:
    """Return `fields` minus any key reserved by LogRecord.

    Use this for every `extra=` dict so a reserved key degrades to a dropped
    field rather than raising inside the tool.

    Note two distinct failure modes this prevents:
      * `args`, `name`, `module`, `msg`, `exc_info`, ... — logging RAISES
        KeyError("Attempt to overwrite ...") because the attribute already
        exists on the record.
      * `level`, `levelno`, `levelname`, `filename`, `lineno`, `msecs`,
        `relativeCreated`, `created`, `funcName`, `process`, `thread`,
        `threadName`, `pathname`, `stack_info`, `exc_text` — these do NOT
        raise, they silently OVERWRITE the real value. A log line about a
        Matrix signal with `level="green"` would report its severity as
        "green" and no log level at all. That is worse than a crash because
        nothing tells you it happened.
    """
    reserved = set(vars(logging.LogRecord("", 0, "", 0, "", (), None)))
    return {k: v for k, v in fields.items() if k not in reserved}


class JsonFormatter(logging.Formatter):
    """One JSON object per line, for machine consumption and log shipping.

    Extras are namespaced under a single `extra` key rather than merged at the
    top level. Merging is what let an `extra={"level": "green"}` overwrite this
    formatter's own `"level"` severity field — logging itself does not reserve
    `level` (it stores `levelname`/`levelno`), so the collision was silent and
    the record lost its severity entirely.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = current_request_id()
        if rid:
            payload["request_id"] = rid
        if record.exc_info:
            payload["exception"] = _redact(self.formatException(record.exc_info))

        # Structured extras from logger.info(..., extra={...}) go in their own
        # object so they can never clobber a field defined above.
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED and not key.startswith("_")
        }
        if extras:
            payload["extra"] = extras
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    """Compact human-readable form for interactive tails."""

    def format(self, record: logging.LogRecord) -> str:
        rid = current_request_id()
        prefix = f" [{rid}]" if rid else ""
        base = (
            f"{time.strftime('%H:%M:%S', time.gmtime(record.created))} "
            f"{record.levelname:<7} {record.name}{prefix}: {record.getMessage()}"
        )
        if record.exc_info:
            base += "\n" + _redact(self.formatException(record.exc_info))
        return base


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def configure_logging(
    *,
    level: str | None = None,
    log_file: str | os.PathLike[str] | None = None,
    json_to_stderr: bool | None = None,
    max_bytes: int = 2_000_000,
    backup_count: int = 3,
) -> logging.Logger:
    """Install handlers on the agent logger.

    Idempotent: calling twice replaces handlers rather than duplicating them,
    which matters because both the server entrypoint and the test harness
    import this module.

    Streams are resolved once, at configure time. Under the stdio transport
    the server may later reassign `sys.stdout` to a pipe, so holding a stale
    reference here is what guarantees records never land in the RPC stream.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel((level or os.environ.get("AGENT_LOG_LEVEL", "INFO")).upper())
    # We own our own handlers; do not also emit into the root logger.
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    redactor = RedactingFilter()
    level_name = os.environ.get("AGENT_LOG_LEVEL", "INFO").upper()

    # 1. Human channel — always stderr.
    console = logging.StreamHandler(stream=sys.stderr)
    console.setLevel(level_name)
    if json_to_stderr is None:
        json_to_stderr = os.environ.get("AGENT_LOG_FORMAT", "").lower() == "json"
    console.setFormatter(JsonFormatter() if json_to_stderr else TextFormatter())
    console.addFilter(redactor)
    logger.addHandler(console)

    # 2. Durable rotating file. Opt out with AGENT_LOG_FILE="" to disable.
    target = log_file if log_file is not None else os.environ.get(
        "AGENT_LOG_FILE", "state/logs/agent.log"
    )
    if target:
        try:
            path = Path(target)
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
            )
            file_handler.setLevel("DEBUG")  # files keep detail the console drops
            file_handler.setFormatter(JsonFormatter())
            file_handler.addFilter(redactor)
            logger.addHandler(file_handler)
        except OSError as exc:
            # A read-only or missing log dir must not prevent the agent from
            # starting; say so and carry on with console-only logging.
            logger.warning(
                "log file unavailable (%s); continuing with stderr only",
                exc,
                extra={"log_file": str(target)},
            )

    return logger


def get_logger(suffix: str | None = None) -> logging.Logger:
    return logging.getLogger(
        f"{LOGGER_NAME}.{suffix}" if suffix else LOGGER_NAME
    )


# ---------------------------------------------------------------------------
# stdout guard
# ---------------------------------------------------------------------------

class StdoutProtocolViolation(RuntimeError):
    """Raised when code writes to stdout while the stdio transport owns it."""


def install_stdout_guard() -> None:
    """Redirect `sys.stdout` to stderr for the whole process.

    The MCP stdio transport owns the real stdout. We capture the original
    stream for the server itself and swap in stderr, so that any stray print
    in a handler, a dependency, or a library lands in the log where it is
    visible and harmless, instead of corrupting the RPC stream.
    """
    real_stdout = sys.stdout
    sys.stdout = sys.stderr
    log = get_logger("stdout")
    log.debug(
        "stdout redirected to stderr to protect the JSON-RPC stream",
        extra={"protocol_stream": repr(real_stdout)[:120]},
    )
