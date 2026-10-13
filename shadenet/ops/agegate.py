"""Operator overrides for the 21+ gate.

Two levers:
  - global mode (settings "agegate.mode": enforce | monitor | off)
  - per-subject overrides: grant (treat as verified) or block (treat as
    unverified even with a valid proof), always with a reason and an expiry.

Not yet consulted by shadenet.zkp.require_zkp_gate. That wiring belongs to the
Steward work, which is also fixing the client-side fail-open activation.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from shadenet.ops import now_iso, read_json, write_json

_FILE = "agegate_overrides.json"
KINDS = ("grant", "block")
MAX_DAYS = 90


def _load() -> dict:
    return read_json(_FILE, {"overrides": []})


def create(subject: str, kind: str, reason: str, days: int, actor: str) -> dict:
    if kind not in KINDS:
        raise ValueError("kind must be grant or block")
    if not subject.strip() or not reason.strip():
        raise ValueError("subject and reason are required")
    if not 1 <= days <= MAX_DAYS:
        raise ValueError(f"overrides last 1-{MAX_DAYS} days")
    o = {
        "id": "age_" + secrets.token_hex(6),
        "subject": subject.strip(),
        "kind": kind,
        "reason": reason.strip()[:500],
        "created_by": actor,
        "created_at": now_iso(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(),
        "revoked": False,
    }
    data = _load()
    data["overrides"].append(o)
    write_json(_FILE, data)
    return o


def revoke(oid: str, actor: str) -> dict:
    data = _load()
    o = next((x for x in data["overrides"] if x["id"] == oid), None)
    if not o:
        raise KeyError(f"no override {oid!r}")
    o.update(revoked=True, revoked_by=actor, revoked_at=now_iso())
    write_json(_FILE, data)
    return o


def active_for(subject: str) -> dict | None:
    now = datetime.now(timezone.utc)
    for o in reversed(_load()["overrides"]):
        if o["subject"] == subject and not o["revoked"] and datetime.fromisoformat(o["expires_at"]) > now:
            return o
    return None


def listing() -> list[dict]:
    now = datetime.now(timezone.utc)
    out = []
    for o in reversed(_load()["overrides"]):
        o = dict(o)
        o["active"] = not o["revoked"] and datetime.fromisoformat(o["expires_at"]) > now
        out.append(o)
    return out
