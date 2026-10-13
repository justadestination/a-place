"""Account recovery for locked-out users (lost passkey / lost phone).

Lifecycle:  pending -> approved (waiting period running) -> executed
                    \\-> denied            \\-> cancelled (by owner or operator)

Recovery hands someone else's account to whoever asks, so:
  - approval needs TOTP step-up (enforced in routes.py),
  - approval starts a waiting period (accounts.recovery_delay_hours) during
    which the owner's existing devices can cancel,
  - execution is a separate, audited step after the period ends.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from shadenet.ops import now_iso, read_json, settings, write_json

_FILE = "recovery.json"
EVIDENCE_KINDS = ("in_person", "venue_vouch", "backup_code", "linked_email", "prior_device_signature", "other")


def _load() -> dict:
    return read_json(_FILE, {"requests": []})


def _save(data: dict) -> None:
    write_json(_FILE, data)


def _find(data: dict, rid: str) -> dict:
    for r in data["requests"]:
        if r["id"] == rid:
            return r
    raise KeyError(f"no recovery request {rid!r}")


def create(account: str, reason: str, *, evidence: list[dict], opened_by: str) -> dict:
    if not account.strip():
        raise ValueError("account is required")
    for e in evidence:
        if e.get("kind") not in EVIDENCE_KINDS:
            raise ValueError(f"evidence kind must be one of {', '.join(EVIDENCE_KINDS)}")
    req = {
        "id": "rec_" + secrets.token_hex(6),
        "account": account.strip(),
        "reason": reason.strip()[:1000],
        "evidence": [{"kind": e["kind"], "note": str(e.get("note", ""))[:500]} for e in evidence],
        "status": "pending",
        "created_at": now_iso(),
        "opened_by": opened_by,
        "history": [{"ts": now_iso(), "by": opened_by, "event": "opened"}],
    }
    data = _load()
    data["requests"].append(req)
    _save(data)
    return req


def approve(rid: str, actor: str) -> dict:
    data = _load()
    req = _find(data, rid)
    if req["status"] != "pending":
        raise ValueError(f"request is {req['status']}, not pending")
    hours = int(settings.get("accounts.recovery_delay_hours"))
    req["status"] = "approved"
    req["executable_after"] = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    req["history"].append({"ts": now_iso(), "by": actor, "event": "approved", "waiting_hours": hours})
    _save(data)
    # TODO(steward task): push a cancel-able notice to the account's existing devices.
    return req


def transition(rid: str, actor: str, to: str, note: str = "") -> dict:
    allowed = {"deny": ("pending",), "cancel": ("pending", "approved")}
    data = _load()
    req = _find(data, rid)
    if req["status"] not in allowed[to]:
        raise ValueError(f"cannot {to} a request that is {req['status']}")
    req["status"] = {"deny": "denied", "cancel": "cancelled"}[to]
    req["history"].append({"ts": now_iso(), "by": actor, "event": req["status"], "note": note[:500]})
    _save(data)
    return req


def execute(rid: str, actor: str) -> dict:
    data = _load()
    req = _find(data, rid)
    if req["status"] != "approved":
        raise ValueError("only approved requests can be executed")
    if datetime.now(timezone.utc) < datetime.fromisoformat(req["executable_after"]):
        raise ValueError(f"waiting period runs until {req['executable_after']}")
    # TODO(steward task): issue a one-time re-enrolment link via shadenet.auth.
    # Until then, refuse rather than pretend.
    raise NotImplementedError("credential reset is not wired to shadenet.auth yet")


def listing(status: str = "") -> list[dict]:
    reqs = _load()["requests"]
    return [r for r in reversed(reqs) if not status or r["status"] == status]
