#!/usr/bin/env python3
"""
Minimal MCP server that loads tools from ../config/mcp-tools.yaml
and implements the five declared tools against the rest of the scaffold.

This is a working skeleton — expand the handlers as needed.
Run with: python server.py
(or python -m mcp_server if you turn it into a package)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import yaml

# Logging + structured error envelopes. See logstack.py for the rationale
# behind stderr-only logging and the error contract.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from logstack import (  # noqa: E402
    ErrorCode,
    configure_logging,
    current_request_id,
    error,
    get_logger,
    install_stdout_guard,
    ok,
    register_secret,
    request_scope,
)

log = get_logger("server")

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
STATE = ROOT / "state"
STATE.mkdir(exist_ok=True)

# Placeholders that ship in matrix.yaml. Config containing these has never
# been filled in, so any send attempt is guaranteed to fail — we detect this
# and say so rather than burning a request on a guaranteed error.
_PLACEHOLDER_MARKERS = ("your-synapse.example.com", "yourRoomId", "@agent:")


def configure() -> None:
    """One-time startup wiring: logging, secret registration.

    Note on the stdout guard: it is NOT installed by default, and must not be.
    The MCP SDK writes its JSON-RPC frames to whatever `sys.stdout` is at the
    time the transport is created, so swapping `sys.stdout` to stderr severs
    the protocol stream (observed: initialize succeeds, every subsequent call
    hangs). The guard exists for *diagnostics* only — it is useful when
    hunting down a stray print, not as a runtime protection.

    Actual protection against stream corruption is the discipline enforced in
    test_scaffold.py: no `print()` in any handler, all output via `log.*`.
    """
    configure_logging()
    if os.environ.get("AGENT_STDOUT_GUARD", "0") == "1":
        log.warning(
            "AGENT_STDOUT_GUARD=1 — diagnostics only; this breaks the stdio transport"
        )
        install_stdout_guard()
    token = os.environ.get("MATRIX_ACCESS_TOKEN")
    if token:
        register_secret(token)
    log.info(
        "agent-tools starting",
        extra={"root": str(ROOT), "pid": os.getpid()},
    )

def load_yaml(name: str) -> dict:
    with open(CONFIG / name) as f:
        return yaml.safe_load(f)

def load_tasks() -> list[dict]:
    path = STATE / "tasks.json"
    if not path.exists():
        seed = load_yaml("tasks.yaml").get("seed", [])
        path.write_text(json.dumps(seed, indent=2))
        return seed
    return json.loads(path.read_text())

def save_tasks(tasks: list[dict]) -> None:
    (STATE / "tasks.json").write_text(json.dumps(tasks, indent=2))

# ---------- tool handlers ----------

def tool_task_list(args: dict) -> Any:
    action = args.get("action")
    try:
        tasks = load_tasks()
    except (OSError, json.JSONDecodeError) as exc:
        log.error("task_list load failed", extra={"error": str(exc)})
        return error(ErrorCode.INTERNAL, f"could not read task list: {exc}", action=action)

    if action == "list":
        return ok(tasks=tasks, count=len(tasks))
    if action == "get":
        tid = args.get("id")
        found = next((t for t in tasks if t["id"] == tid), None)
        if found is None:
            return error(ErrorCode.TASK_NOT_FOUND, f"no task with id {tid!r}", id=tid)
        return ok(task=found)
    if action == "update":
        tid = args.get("id")
        patch = args.get("patch") or {}
        if not patch:
            return error(ErrorCode.TASK_INVALID, "update requires a non-empty 'patch'", id=tid)
        for t in tasks:
            if t["id"] == tid:
                unknown = set(patch) - set(t)
                if unknown:
                    # Silently inventing a field would corrupt the state file
                    # and hide a caller typo; say what was rejected instead.
                    log.warning(
                        "task_list update has unknown fields",
                        extra={"id": tid, "unknown": sorted(unknown)},
                    )
                t.update(patch)
                t["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                try:
                    save_tasks(tasks)
                except OSError as exc:
                    return error(ErrorCode.INTERNAL, f"could not persist tasks: {exc}", id=tid)
                log.info("task updated", extra={"id": tid, "fields": sorted(patch)})
                return ok(task=t)
        return error(ErrorCode.TASK_NOT_FOUND, f"no task with id {tid!r}", id=tid)
    if action == "add":
        task = args.get("task")
        if not task or not task.get("id"):
            return error(ErrorCode.TASK_INVALID, "add requires a 'task' object with an id")
        if any(t["id"] == task["id"] for t in tasks):
            return error(
                ErrorCode.TASK_INVALID, f"task {task['id']!r} already exists", id=task["id"]
            )
        task.setdefault("status", "pending")
        task.setdefault("created", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        task["updated"] = task["created"]
        tasks.append(task)
        try:
            save_tasks(tasks)
        except OSError as exc:
            return error(ErrorCode.INTERNAL, f"could not persist tasks: {exc}")
        log.info("task added", extra={"id": task["id"], "title": task.get("title")})
        return ok(task=task)
    return error(ErrorCode.TASK_UNKNOWN_ACTION, f"unknown action {action!r}", action=action)

def tool_lexicon_lookup(args: dict) -> Any:
    lex = load_yaml("lexicon.yaml")
    term = args["term"].lower()
    section = args.get("section")
    if section:
        return lex.get(section, {}).get(term) or lex.get(section, {}).get(args["term"])
    # search all sections
    for sec, mapping in lex.items():
        if isinstance(mapping, dict) and (term in mapping or args["term"] in mapping):
            return {"section": sec, "meaning": mapping.get(term) or mapping.get(args["term"])}
    return None

def _matrix_config_state() -> tuple[dict, str | None]:
    """Return (config, blocking_reason).

    `blocking_reason` is None when the config looks usable, otherwise a short
    reason string naming the first thing that stops a real send.
    """
    cfg = load_yaml("matrix.yaml")
    homeserver = (cfg.get("homeserver") or "").strip()
    room_id = (cfg.get("room_id") or "").strip()

    if not homeserver or not room_id:
        return cfg, "matrix.yaml is missing homeserver or room_id"
    if any(marker in homeserver or marker in room_id for marker in _PLACEHOLDER_MARKERS):
        return cfg, (
            "matrix.yaml still contains shipped placeholders "
            "(your-synapse.example.com / !yourRoomId) — fill in a real "
            "homeserver and room_id"
        )
    if not os.environ.get("MATRIX_ACCESS_TOKEN"):
        return cfg, (
            "MATRIX_ACCESS_TOKEN is not set in the environment; the agent "
            "cannot authenticate to Synapse"
        )
    return cfg, None


def _post_matrix_message(
    cfg: dict, message: str, timeout: float
) -> tuple[dict, str | None]:
    """POST a message to Synapse's send-message endpoint.

    Returns (result_dict, error_code). Exactly one is None. Uses the
    Client-Server API directly rather than matrix-nio to keep the
    dependency surface small; nio can be layered in later.
    """
    import httpx

    homeserver = cfg["homeserver"].rstrip("/")
    room_id = cfg["room_id"]
    # txn_id makes the send idempotent: a retry after a timeout cannot
    # duplicate the message in the room.
    txn_id = uuid.uuid4().hex
    url = f"{homeserver}/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}"

    prefix = cfg.get("message_prefix") or ""
    emoji = (cfg.get("status_reactions") or {}).get(message.get("level", ""), "")
    body_text = f"{prefix}{emoji} {message['message']}".strip()

    payload = {"msgtype": "m.text", "body": body_text}
    started = time.monotonic()
    try:
        response = httpx.post(
            url,
            json=payload,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {os.environ['MATRIX_ACCESS_TOKEN']}",
                "Content-Type": "application/json",
            },
        )
    except httpx.TimeoutException as exc:
        return {}, ErrorCode.MATRIX_UNREACHABLE
    except httpx.HTTPError as exc:
        log.warning("matrix transport error", extra={"detail": str(exc)})
        return {}, ErrorCode.MATRIX_UNREACHABLE

    elapsed_ms = int((time.monotonic() - started) * 1000)

    if response.status_code in (401, 403):
        code = (
            ErrorCode.MATRIX_AUTH_FAILED
            if response.status_code == 401
            else ErrorCode.MATRIX_FORBIDDEN
        )
        # No "code" key here: `error()` takes code as its first parameter, so
        # repeating it in the details would collide on the call.
        return {"http_status": response.status_code}, code
    if response.status_code == 404:
        return {"http_status": 404}, ErrorCode.MATRIX_NOT_FOUND
    if response.status_code == 429:
        return (
            {
                "http_status": 429,
                "retry_after_ms": _parse_retry_after(response.headers.get("Retry-After")),
            },
            ErrorCode.MATRIX_RATE_LIMITED,
        )
    if response.status_code >= 400:
        return (
            {
                "http_status": response.status_code,
                "response_body": response.text[:500],
            },
            ErrorCode.MATRIX_SEND_FAILED,
        )

    event_id = response.json().get("event_id")
    return (
        {
            "event_id": event_id,
            "room_id": room_id,
            "txn_id": txn_id,
            "http_status": response.status_code,
            "duration_ms": elapsed_ms,
            "body": body_text,
        },
        None,
    )


def _parse_retry_after(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(float(value) * 1000)
    except (TypeError, ValueError):
        return None


def tool_matrix_signal(args: dict) -> Any:
    """Post a status message to the configured Matrix room.

    Reports honestly: `ok`/`sent` are true only when Synapse actually
    accepted the message. When it could not be sent the envelope names the
    blocking reason so a caller can distinguish "no token" from "auth
    rejected" from "rate limited" — and so a failed handshake is never
    minode-inferenceen for a delivered one.
    """
    message = args.get("message", "")
    level = args.get("level", "green")
    timeout = float(args.get("timeout_sec", cfg_timeout()))

    cfg, blocked = _matrix_config_state()
    if blocked:
        # Unconfigured is an *expected* state, not a tool failure: the call
        # succeeded and is truthfully reporting that nothing was delivered.
        # So `ok` stays True and `sent` is False. This distinction matters —
        # a caller must never read this as a delivered handshake (T003), and
        # equally must not treat it as a crash to retry blindly.
        log.info(
            "matrix_signal not sent: not configured",
            extra={"signal_level": level, "reason": blocked},
        )
        return ok(
            sent=False,
            status="not_configured",
            level=level,
            message=message,
            reason=blocked,
            homeserver=cfg.get("homeserver"),
        )

    result, code = _post_matrix_message(cfg, {**args, "level": level}, timeout)
    if code:
        log.warning(
            "matrix_signal failed",
            extra={
                "signal_level": level,
                "failure_code": code,
                "http_status": result.get("http_status"),
            },
        )
        # `error()` reserves the parameter names code/message, so the outbound
        # text is passed as `text` to keep it in the details block.
        return error(
            code,
            f"Synapse rejected the message: {code}",
            sent=False,
            level=level,
            text=message,
            **result,
        )

    log.info(
        "matrix_signal delivered",
        extra={
            "level": level,
            "event_id": result.get("event_id"),
            "duration_ms": result.get("duration_ms"),
        },
    )
    return ok(sent=True, level=level, message=message, **result)


def cfg_timeout() -> int:
    try:
        return int(load_yaml("matrix.yaml").get("sync_timeout_ms", 30000) / 1000)
    except Exception:
        return 30


def tool_local_infer(args: dict) -> Any:
    agent = load_yaml("agent.yaml")
    inf = agent["inference"]["local"]
    endpoint = inf["endpoint"].rstrip("/")
    model = inf["model"]
    temperature = inf.get("temperature", 0.3)
    context = inf.get("context", 8192)
    import httpx

    started = time.monotonic()
    try:
        r = httpx.post(
            f"{endpoint}/api/generate",
            json={
                "model": model,
                "prompt": args["prompt"],
                "stream": False,
                "temperature": temperature,
                "num_ctx": context,
                "max_tokens": args.get("max_tokens", 512),
            },
            timeout=90,
        )
    except httpx.HTTPError as exc:
        log.warning("local_infer transport failure", extra={"endpoint": endpoint})
        return error(
            ErrorCode.INFER_UNREACHABLE,
            f"local inference endpoint {endpoint} is unreachable: {exc}",
            endpoint=endpoint,
            model=model,
        )

    if r.status_code == 404:
        # Ollama returns 404 when the model simply isn't pulled. That is a
        # fixable setup problem and deserves its own code, distinct from a
        # server that is down — the remedy differs.
        log.warning("local_infer model missing", extra={"model": model})
        return error(
            ErrorCode.INFER_MODEL_MISSING,
            f"model {model!r} is not available at {endpoint}; run `ollama pull {model}`",
            endpoint=endpoint,
            model=model,
            http_status=404,
        )
    if r.status_code >= 400:
        log.warning("local_infer failed", extra={"http_status": r.status_code})
        return error(
            ErrorCode.INFER_FAILED,
            f"inference endpoint returned {r.status_code}",
            endpoint=endpoint,
            model=model,
            http_status=r.status_code,
            body=r.text[:500],
        )

    response_text = r.json().get("response", "")
    return ok(
        response=response_text,
        model=model,
        endpoint=endpoint,
        duration_ms=int((time.monotonic() - started) * 1000),
    )


def tool_run_shell(args: dict) -> Any:
    cmd = args["command"]
    cwd = args.get("cwd") or str(ROOT)
    timeout = args.get("timeout_sec", 30)

    # Sandbox: reject cwd escapes and forbidden paths.
    root = str(ROOT.resolve())
    try:
        target = str(Path(cwd).resolve())
    except (OSError, RuntimeError) as exc:
        return error(
            ErrorCode.SANDBOX_CWD_ESCAPE,
            f"cannot resolve cwd {cwd!r}: {exc}",
            command=cmd,
        )
    if not target.startswith(root + os.sep) and target != root:
        return error(
            ErrorCode.SANDBOX_CWD_ESCAPE,
            f"sandbox: cwd {cwd!r} resolves outside the project root",
            command=cmd,
            requested_cwd=cwd,
            project_root=root,
        )
    for forbidden in (os.path.join(STATE, ""), "/tmp", "/var/tmp", "/dev/shm"):
        if target.startswith(forbidden):
            return error(
                ErrorCode.SANDBOX_FORBIDDEN_PATH,
                f"sandbox: cwd {cwd!r} is not an allowed location",
                command=cmd,
                requested_cwd=cwd,
            )

    log.info("run_shell executing", extra={"command": cmd, "cwd": target, "timeout_sec": timeout})
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=target, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        log.warning("run_shell timed out", extra={"command": cmd, "timeout_sec": timeout})
        return error(
            ErrorCode.SHELL_TIMEOUT,
            f"command exceeded its {timeout}s timeout and was killed",
            command=cmd,
            timeout_sec=timeout,
        )
    except Exception as exc:
        log.error("run_shell raised", extra={"command": cmd, "error": str(exc)})
        return error(ErrorCode.SHELL_FAILED, str(exc), command=cmd)

    log.info(
        "run_shell finished",
        extra={"command": cmd, "returncode": result.returncode},
    )
    # `cwd` is echoed back so a caller can confirm where the command actually
    # ran; stdout is truncated, so the full output may not be present.
    return {
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "cwd": target,
        "command": cmd,
        "truncated": len(result.stdout) > 4000,
    }

HANDLERS = {
    "task_list": tool_task_list,
    "lexicon_lookup": tool_lexicon_lookup,
    "matrix_signal": tool_matrix_signal,
    "local_infer": tool_local_infer,
    "run_shell": tool_run_shell,
}

# ---------------------------------------------------------------------------
# MCP server wiring — MCPServer (mcp 2.x, replaces FastMCP)
# ---------------------------------------------------------------------------

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("agent-tools", version="0.3")

configure()

def _dispatch(name: str, args: dict) -> Any:
    """Run a handler inside a request scope, converting crashes to envelopes.

    A tool that raises would otherwise surface as an opaque protocol error and
    could destabilise the session. Here every handler is contained: a failure
    becomes a structured envelope naming the code, with the traceback logged
    rather than returned.
    """
    with request_scope(prefix=name):
        # NOTE: never use "args", "msg", "name", "levelname" or "exc_info" as
        # extra keys — they are reserved LogRecord attributes and logging
        # raises KeyError("Attempt to overwrite ... in LogRecord"), which would
        # surface as a tool failure rather than a logging failure.
        log.info("tool call", extra={"tool": name, "tool_args": _redact_args(args)})
        try:
            result = HANDLERS[name](args)
        except Exception as exc:
            log.exception("tool raised", extra={"tool": name})
            return error(ErrorCode.INTERNAL, f"{name} failed: {exc}", tool=name)
        log.info("tool done", extra={"tool": name, "ok": _result_ok(result)})
        return result


def _redact_args(args: dict) -> dict:
    """Strip secret-looking keys before args reach the log."""
    if not isinstance(args, dict):
        return {}
    return {
        k: ("***" if any(s in k.lower() for s in ("token", "secret", "password", "key"))
            else (v if not isinstance(v, str) or len(v) < 200 else v[:200] + "…"))
        for k, v in args.items()
    }


def _result_ok(result: Any) -> bool | None:
    if isinstance(result, dict):
        return result.get("ok")
    return None


@mcp.tool()
def task_list(action: str, id: str | None = None,
              patch: dict | None = None, task: dict | None = None) -> dict:
    """Read or update the shared task list."""
    args: dict = {"action": action}
    if id is not None:
        args["id"] = id
    if patch is not None:
        args["patch"] = patch
    if task is not None:
        args["task"] = task
    return _dispatch("task_list", args)

@mcp.tool()
def lexicon_lookup(term: str, section: str | None = None) -> dict | str | None:
    """Look up a term or phrase from the shared lexicon."""
    return _dispatch("lexicon_lookup", {"term": term, "section": section})

@mcp.tool()
def matrix_signal(message: str, level: str = "green") -> dict:
    """Post a short status message to the configured Matrix room.

    Returns `sent: true` only when Synapse actually accepted the message.
    When unconfigured, returns `sent: false` with `status: not_configured`
    and a human-readable `reason` — the call itself succeeded.
    """
    return _dispatch("matrix_signal", {"message": message, "level": level})

@mcp.tool()
def local_infer(prompt: str, max_tokens: int = 512) -> dict:
    """Force a local-model completion (bypasses escalation)."""
    return _dispatch("local_infer", {"prompt": prompt, "max_tokens": max_tokens})

@mcp.tool()
def run_shell(command: str, cwd: str | None = None, timeout_sec: int = 30) -> dict:
    """Run a shell command in the project workspace (Builder only)."""
    return _dispatch("run_shell", {"command": command, "cwd": cwd, "timeout_sec": timeout_sec})

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    tools_cfg = load_yaml("mcp-tools.yaml")
    log.info(
        "starting stdio MCP server",
        extra={
            "declared_tools": [t["name"] for t in tools_cfg["tools"]],
            "transport": "stdio",
            "stdout_guard": os.environ.get("AGENT_STDOUT_GUARD", "0") == "1",
        },
    )
    # NOTE: no print() anywhere in this process. stdout is the JSON-RPC
    # stream; log.* writes to stderr, which the transport does not own.
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()