"""Owner and operator edits for a venue (Task 2.14).

The overlay is a JSON file. Tests point VENUE_EDITS_PATH at a temp file.
The first person to claim a venue owns it. Anyone else is refused unless
their username is listed in NIGHTCAL_OPERATORS.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_lock = threading.Lock()


def edits_path() -> Path:
    raw = os.environ.get("VENUE_EDITS_PATH")
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent.parent / "data" / "venue_edits.json"


def _operators() -> set[str]:
    return {part.strip() for part in os.environ.get("NIGHTCAL_OPERATORS", "").split(",") if part.strip()}


def _blank(venue_id: str) -> dict[str, Any]:
    return {
        "venue_id": venue_id,
        "owner_user_id": None,
        "owner_username": None,
        "name": "",
        "address": "",
        "blurbs": [],
        "events": [],
    }


def _load() -> dict[str, Any]:
    path = edits_path()
    if not path.is_file():
        return {"venues": {}}
    try:
        data = json.loads(path.read_text() or "{}")
    except json.JSONDecodeError:
        return {"venues": {}}
    if not isinstance(data, dict) or not isinstance(data.get("venues"), dict):
        return {"venues": {}}
    return data


def _save(data: dict[str, Any]) -> None:
    path = edits_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _may(record: dict[str, Any], user: dict[str, Any]) -> bool:
    if record.get("owner_user_id") and record["owner_user_id"] == user.get("id"):
        return True
    return str(user.get("username") or "") in _operators()


def _require_id(venue_id: str) -> str:
    venue_id = str(venue_id or "").strip()
    if not venue_id:
        raise ValueError("venue_id is required")
    return venue_id


def get_overlay(venue_id: str) -> dict[str, Any]:
    venue_id = str(venue_id or "").strip()
    with _lock:
        data = _load()
    record = data["venues"].get(venue_id) if venue_id else None
    if not record:
        return _blank(venue_id)
    return {
        "venue_id": venue_id,
        "name": record.get("name") or "",
        "address": record.get("address") or "",
        "blurbs": list(record.get("blurbs") or []),
        "events": list(record.get("events") or []),
    }


def claim(venue_id: str, user: dict[str, Any]) -> dict[str, Any]:
    venue_id = _require_id(venue_id)
    with _lock:
        data = _load()
        record = data["venues"].get(venue_id) or _blank(venue_id)
        if record.get("owner_user_id") and not _may(record, user):
            raise PermissionError("You cannot edit someone else's venue")
        if not record.get("owner_user_id"):
            record["owner_user_id"] = user["id"]
            record["owner_username"] = user.get("username")
        data["venues"][venue_id] = record
        _save(data)
        return record_public(record)


def record_public(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "venue_id": record.get("venue_id"),
        "name": record.get("name") or "",
        "address": record.get("address") or "",
        "blurbs": list(record.get("blurbs") or []),
        "events": list(record.get("events") or []),
        "owner_username": record.get("owner_username"),
    }


def update_info(venue_id: str, user: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    venue_id = _require_id(venue_id)
    with _lock:
        data = _load()
        record = data["venues"].get(venue_id)
        if not record or not _may(record, user):
            raise PermissionError("You cannot edit someone else's venue")
        if fields.get("name"):
            record["name"] = str(fields["name"]).strip()
        if fields.get("address"):
            record["address"] = str(fields["address"]).strip()
        data["venues"][venue_id] = record
        _save(data)
        return record_public(record)


def add_blurb(venue_id: str, user: dict[str, Any], title: str, content: str) -> dict[str, Any]:
    venue_id = _require_id(venue_id)
    title = str(title or "").strip()
    content = str(content or "").strip()
    if not title or not content:
        raise ValueError("A news blurb needs a title and some text")
    with _lock:
        data = _load()
        record = data["venues"].get(venue_id)
        if not record or not _may(record, user):
            raise PermissionError("You cannot edit someone else's venue")
        record.setdefault("blurbs", []).insert(0, {
            "title": title,
            "content": content,
            "date": datetime.now(timezone.utc).date().isoformat(),
        })
        data["venues"][venue_id] = record
        _save(data)
        return record_public(record)


def add_event(venue_id: str, user: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    venue_id = _require_id(venue_id)
    title = str(event.get("title") or "").strip()
    if not title:
        raise ValueError("A show needs a title")
    with _lock:
        data = _load()
        record = data["venues"].get(venue_id)
        if not record or not _may(record, user):
            raise PermissionError("You cannot edit someone else's venue")
        record.setdefault("events", []).insert(0, {
            "id": f"evt_{len(record.get('events') or []) + 1}",
            "title": title,
            "date": str(event.get("date") or ""),
            "start": str(event.get("start") or ""),
            "performers": [],
        })
        data["venues"][venue_id] = record
        _save(data)
        return record_public(record)
