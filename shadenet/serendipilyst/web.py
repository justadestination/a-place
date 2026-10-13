"""HTTP routes for the sheet and the deal commands, served by the NightCal API.

- ``GET  /api/flags/sheet``: public pins and offers. No Steward addresses.
- ``GET  /api/flags/mine``: the signed-in Steward's own flags and nodes.
- ``POST /api/flags``: ``{"command": "upsert" | "deal", "args": {...}}``,
  run through the steward command engine with the actor set here.

The actor is the signed-in Steward. Until Stewards carry their own keypair,
a session's account id maps to a stable address with a keyed hash; the key
lives next to the flag database and never leaves the server. When the
keypair lands, ``steward_address`` is the one function to replace.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shadenet.serendipilyst import get_store, list_business_nodes, list_personal_flags, sheet
from shadenet.steward.command_engine import execute

_STATUS = {
    "scope_denied": 403,
    "not_found": 404,
    "busy": 503,
    "model_unavailable": 503,
    "chat_unavailable": 503,
    "listings_closed": 409,
    "limit_reached": 409,
    "stale_terms": 409,
    "release_undecided": 409,
}
_key: bytes | None = None


def _actor_key() -> bytes:
    global _key
    if _key is not None:
        return _key
    raw = os.environ.get("SERENDIPILYST_ACTOR_KEY", "")
    if raw:
        _key = raw.encode()
        return _key
    db_path = get_store().db_path
    if db_path == ":memory:":
        _key = secrets.token_bytes(32)
        return _key
    path = Path(db_path).with_suffix(".key")
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(secrets.token_bytes(32))
    _key = path.read_bytes()
    return _key


def steward_address(account_id: str) -> str:
    digest = hmac.new(_actor_key(), account_id.encode(), hashlib.sha256).hexdigest()[:24]
    return f"a2a://agent/s_{digest}"


def _mine(actor: str) -> dict[str, Any]:
    store = get_store()
    flags = [
        {k: v for k, v in flag.items() if k != "owner"}
        for flag in list_personal_flags(store, active_only=False)
        if flag["owner"] == actor
    ]
    nodes = [
        {k: v for k, v in node.items() if k != "controller"}
        for node in list_business_nodes(store, active_only=False)
        if node["controller"] == actor
    ]
    return {"flags": flags, "nodes": nodes}


def handle(method: str, path: str, body: dict | None, account_id: str | None) -> tuple[int, dict]:
    """One request. ``account_id`` is None when nobody is signed in."""
    if method == "GET" and path == "/api/flags/sheet":
        return 200, sheet()
    if not account_id:
        return 401, {"error": "Sign in, and your Steward can do this for you."}
    actor = steward_address(account_id)
    if method == "GET" and path == "/api/flags/mine":
        return 200, _mine(actor)
    if method != "POST" or path != "/api/flags":
        return 404, {"error": "not found"}
    command = {"upsert": "flags.upsert", "deal": "flags.deal"}.get(str((body or {}).get("command") or ""))
    args = (body or {}).get("args")
    if not command or not isinstance(args, dict):
        return 400, {"error": 'send {"command": "upsert" | "deal", "args": {...}}'}
    envelope = {
        "messageId": str(uuid.uuid4()),
        "idempotencyKey": str((body or {}).get("idempotencyKey") or uuid.uuid4()),
        "from": actor,
        "command": command,
        "args": args,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    result = execute(envelope, actor)
    if result.get("ok"):
        return 200, result
    code = str((result.get("error") or {}).get("code") or "")
    return _STATUS.get(code, 400), result
