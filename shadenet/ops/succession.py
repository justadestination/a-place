"""Venue custodianship and succession.

Every venue should have at least `venues.min_custodians` people who can manage
it, so one manager quitting or being fired never orphans the listing.

A succession (adding/removing a custodian against the venue's wishes, e.g. the
only manager left) runs a waiting period during which the current custodians
are notified and can object.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from shadenet.ops import now_iso, read_json, write_json
from shadenet.ops import settings

_FILE = "venue_custodians.json"
ROLES = ("owner", "manager", "staff")


def _load() -> dict:
    return read_json(_FILE, {"venues": {}, "successions": []})


def _save(data: dict) -> None:
    write_json(_FILE, data)


def add_custodian(venue_id: str, account: str, role: str, actor: str) -> dict:
    if role not in ROLES:
        raise ValueError(f"role must be one of {', '.join(ROLES)}")
    data = _load()
    custodians = data["venues"].setdefault(venue_id, [])
    if any(c["account"] == account for c in custodians):
        raise ValueError(f"{account} is already a custodian of {venue_id}")
    custodians.append({"account": account, "role": role, "added_by": actor, "added_at": now_iso()})
    _save(data)
    return {"venue_id": venue_id, "custodians": custodians}


def remove_custodian(venue_id: str, account: str, actor: str) -> dict:
    data = _load()
    custodians = data["venues"].get(venue_id, [])
    remaining = [c for c in custodians if c["account"] != account]
    if len(remaining) == len(custodians):
        raise KeyError(f"{account} is not a custodian of {venue_id}")
    if not remaining:
        raise ValueError("can't remove the last custodian; open a succession instead")
    data["venues"][venue_id] = remaining
    _save(data)
    return {"venue_id": venue_id, "custodians": remaining}


def open_succession(venue_id: str, new_account: str, remove_account: str, reason: str, actor: str) -> dict:
    hours = int(settings.get("venues.succession_delay_hours"))
    s = {
        "id": "suc_" + secrets.token_hex(6),
        "venue_id": venue_id,
        "add": new_account,
        "remove": remove_account or "",
        "reason": reason[:1000],
        "status": "waiting",
        "opened_by": actor,
        "opened_at": now_iso(),
        "effective_after": (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(),
    }
    data = _load()
    data["successions"].append(s)
    _save(data)
    # TODO(steward task): notify current custodians so they can object.
    return s


def complete_succession(sid: str, actor: str) -> dict:
    data = _load()
    s = next((x for x in data["successions"] if x["id"] == sid), None)
    if not s:
        raise KeyError(f"no succession {sid!r}")
    if s["status"] != "waiting":
        raise ValueError(f"succession is {s['status']}")
    if datetime.now(timezone.utc) < datetime.fromisoformat(s["effective_after"]):
        raise ValueError(f"waiting period runs until {s['effective_after']}")
    custodians = data["venues"].setdefault(s["venue_id"], [])
    custodians[:] = [c for c in custodians if c["account"] != s["remove"]]
    if not any(c["account"] == s["add"] for c in custodians):
        custodians.append({"account": s["add"], "role": "owner", "added_by": actor, "added_at": now_iso(), "via": sid})
    s.update(status="completed", completed_by=actor, completed_at=now_iso())
    _save(data)
    return s


def cancel_succession(sid: str, actor: str, note: str = "") -> dict:
    data = _load()
    s = next((x for x in data["successions"] if x["id"] == sid), None)
    if not s or s["status"] != "waiting":
        raise ValueError("only waiting successions can be cancelled")
    s.update(status="cancelled", cancelled_by=actor, note=note[:500])
    _save(data)
    return s


def overview(venues: list[dict]) -> dict:
    """Join known venues with their custodians; flag the ones below the minimum."""
    data = _load()
    need = int(settings.get("venues.min_custodians"))
    rows = []
    for v in venues:
        cs = data["venues"].get(v["id"], [])
        rows.append({"venue_id": v["id"], "name": v.get("name", v["id"]), "custodians": cs, "at_risk": len(cs) < need})
    rows.sort(key=lambda r: (not r["at_risk"], r["name"].lower()))
    return {"min_custodians": need, "venues": rows, "successions": list(reversed(data["successions"]))}
