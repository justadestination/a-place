"""Add, correct, and take down shows without deleting a citation.

An agent writes a listing on the `agent` source, with a public page as the
source url, and resolution turns that listing into the event the sheet
shows. A downtown listing is never rewritten: a correction sits beside it,
and the sheet prefers the correction. Taking a show down records a change
and leaves the listing row where it is.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from nightcal.fill import AGENT_SOURCE
from nightcal.surface import load_rows
from towncrier.normalize import normalize_title
from towncrier.resolve import Resolver
from towncrier.store import Store, stable_id

LA = ZoneInfo("America/Los_Angeles")
KINDS = {"music", "comedy", "show", "trivia", "other", "trucks", "market"}
STATUSES = {"EventScheduled", "EventCancelled", "EventPostponed", "EventRescheduled"}
_EVENT_ID = re.compile(r"evt_[0-9a-f]{16}")
_UNSET = object()


class EventWriteError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def list_events(store: Store, query: dict | None = None) -> dict:
    query = query or {}
    hidden_only = _flag(query.get("hidden"))
    _venues, events, _hidden = load_rows(store, include_hidden=hidden_only)
    if hidden_only:
        events = [event for event in events if event.get("suppressed")]
    date = _one(query.get("date"))
    venue_id = _one(query.get("venueId"))
    kind = _one(query.get("kind"))
    chosen = []
    for event in events:
        if date and event.get("date") != date:
            continue
        if venue_id and event.get("venueId") != venue_id:
            continue
        if kind and event.get("kind") != kind:
            continue
        chosen.append(_public(store, event))
    return {"events": chosen}


def get_event(store: Store, event_id: str) -> dict:
    event_id = _follow(store, event_id)
    event = _find(store, event_id, include_hidden=True)
    if event is None:
        raise EventWriteError("no show with that id", 404)
    return {"event": _public(store, event)}


def create_event(store: Store, body: dict) -> tuple[str, dict]:
    if not isinstance(body, dict):
        raise EventWriteError("expected a JSON object")
    fields = _statement(store, body, base=None)
    external_id = _external_id(body.get("externalId"), fields["source_url"])
    with store.tx():
        listing_id, action = _write_listing(store, external_id, fields, suppressed=False)
        Resolver(store).resolve()
        event_id = _event_for_listing(store, listing_id)
        _set_rail(store, event_id, "shown", fields["source_url"])
    event = _find(store, event_id, include_hidden=True)
    if event is None:
        raise EventWriteError("the show was stored but did not resolve", 500)
    return action, {"action": "created" if action == "new" else "updated", "event": _public(store, event)}


def update_event(store: Store, event_id: str, body: dict) -> dict:
    event_id = _follow(store, event_id)
    if not isinstance(body, dict):
        raise EventWriteError("expected a JSON object")
    current = _find(store, event_id, include_hidden=True)
    if current is None:
        raise EventWriteError("no show with that id", 404)
    listing = _agent_listing(store, event_id)
    suppressed = body.get("suppressed")
    if suppressed is not None and not isinstance(suppressed, bool):
        raise EventWriteError("suppressed has to be true or false")
    if "suppressed" in body and not _touches(body):
        if suppressed:
            return remove_event(store, event_id, body)
        with store.tx():
            if listing is not None:
                _mark_suppressed(store, int(listing["id"]), False)
            _set_rail(store, event_id, "shown", "restored")
        event = _find(store, event_id, include_hidden=True)
        if event is None:
            raise EventWriteError("no show with that id", 404)
        return {"action": "restored", "event": _public(store, event)}
    base = _base_from(current, listing)
    if not _touches(body):
        raise EventWriteError("nothing to change")
    fields = _statement(store, body, base=base)
    external_id = listing["external_id"] if listing else f"edit:{event_id}"
    with store.tx():
        listing_id, _action = _write_listing(
            store, external_id, fields, suppressed=bool(suppressed),
        )
        Resolver(store).resolve()
        new_id = _event_for_listing(store, listing_id)
        # The downtown copy keeps its own listing. If the correction no
        # longer clusters with it, hide that copy so the sheet shows one show.
        # The old id still answers, and follows the show it became.
        if new_id != event_id:
            store.record_change(event_id, "successor", event_id, new_id, reason=fields["source_url"])
            if _still_linked(store, event_id):
                _set_rail(store, event_id, "hidden", fields["source_url"])
        _set_rail(store, new_id, "hidden" if suppressed else "shown", fields["source_url"])
    event = _find(store, new_id, include_hidden=True)
    if event is None:
        raise EventWriteError("the show was stored but did not resolve", 500)
    action = "removed" if event.get("suppressed") else "updated"
    return {"action": action, "event": _public(store, event)}


def remove_event(store: Store, event_id: str, body: dict | None) -> dict:
    event_id = _follow(store, event_id)
    body = body or {}
    if not isinstance(body, dict):
        raise EventWriteError("expected a JSON object")
    current = _find(store, event_id, include_hidden=True)
    if current is None:
        raise EventWriteError("no show with that id", 404)
    source_url = _public_url(body.get("sourceUrl") or body.get("source_url"))
    reason = body.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise EventWriteError("reason has to be text")
    note = source_url if not (reason or "").strip() else f"{source_url} {reason.strip()}"
    with store.tx():
        listing = _agent_listing(store, event_id)
        if listing is not None:
            _mark_suppressed(store, int(listing["id"]), True)
        # No agent listing yet: the downtown row stays as it was. The change
        # log is what takes the resolved show off the sheet.
        _set_rail(store, event_id, "hidden", note)
    event = _find(store, event_id, include_hidden=True)
    if event is None:
        raise EventWriteError("no show with that id", 404)
    return {"action": "removed", "event": _public(store, event)}


def _public(store: Store, event: dict) -> dict:
    listings = store.query(
        """
        SELECT l.source_id, l.url, l.title_raw, l.starts_at, l.status, l.raw_json
        FROM listings l
        JOIN event_listings el ON el.listing_id = l.id
        WHERE el.event_id = ?
        ORDER BY l.id
        """,
        (event["id"],),
    )
    return {
        "id": event["id"],
        "title": event["title"],
        "date": event["date"],
        "startsAt": event.get("startsAt") or "",
        "endsAt": event.get("endsAt") or "",
        "startLabel": event.get("startLabel") or "",
        "endLabel": event.get("endLabel") or "",
        "venue": event.get("venue") or "",
        "venueId": event.get("venueId") or "",
        "kind": event.get("kind") or "other",
        "status": event.get("status") or "EventScheduled",
        "sourceUrl": event.get("sourceUrl") or "",
        "sourceName": event.get("sourceName") or "",
        "suppressed": bool(event.get("suppressed")),
        "score": event.get("score") or 0,
        "listings": [
            {
                "source": row["source_id"],
                "url": row["url"] or "",
                "title": row["title_raw"] or "",
                "startsAt": row["starts_at"] or "",
                "status": row["status"] or "",
                "suppressed": bool(_raw(row["raw_json"]).get("suppressed")),
            }
            for row in listings
        ],
    }


def _statement(store: Store, body: dict, base: dict | None) -> dict:
    """Fields for one agent listing. `base` is the show being corrected."""
    title = _text(body, "title", required=base is None, limit=300)
    if title is _UNSET:
        title = base["title"]
    starts = _when(body, "startsAt", required=base is None)
    if starts is _UNSET:
        starts = base["starts"]
    ends = _when(body, "endsAt", required=False, allow_null=True)
    if ends is _UNSET:
        ends = None if base is None else base["ends"]
    if ends is not None and ends < starts:
        # A move that does not mention the old end is not a claim that the
        # show still finishes on the previous night.
        if "endsAt" in body or "ends_at" in body:
            raise EventWriteError("endsAt is before startsAt")
        ends = None
    if "sourceUrl" in body or "source_url" in body or base is None:
        source_url = _public_url(body.get("sourceUrl", body.get("source_url")))
    else:
        source_url = base["source_url"]
        if not source_url:
            raise EventWriteError("a show needs a public sourceUrl")
    kind = _choice(body, "kind", KINDS, "kind")
    if kind is _UNSET:
        kind = "other" if base is None else base["kind"]
    status = _choice(body, "status", STATUSES, "status")
    if status is _UNSET:
        status = "EventScheduled" if base is None else base["status"]
    description = _text(body, "description", required=False, limit=2000)
    if description is _UNSET:
        description = None if base is None else base["description"]
    venue_id, venue_name = _venue(store, body, base)
    local = starts.astimezone(LA)
    return {
        "title": title,
        "title_norm": normalize_title(title),
        "starts": starts,
        "ends": ends,
        "source_url": source_url,
        "kind": kind,
        "status": status,
        "description": description,
        "venue_id": venue_id,
        "venue_name": venue_name,
        "local_date": local.date().isoformat(),
    }


def _venue(store: Store, body: dict, base: dict | None) -> tuple[str | None, str | None]:
    has_id = "venueId" in body
    has_name = "venue" in body
    if not has_id and not has_name:
        if base is None:
            return None, None
        return base["venue_id"], base["venue_name"]
    venue_id = body.get("venueId") if has_id else None
    venue_name = body.get("venue") if has_name else None
    if venue_id is None and not has_name:
        return None, None
    if venue_id is None and isinstance(venue_name, str) and not venue_name.strip():
        return None, None
    if has_id and venue_id is not None and not isinstance(venue_id, str):
        raise EventWriteError("venueId has to be a room id")
    if has_name and venue_name is not None and not isinstance(venue_name, str):
        raise EventWriteError("venue has to be a room name")
    return _match_venue(
        store,
        (venue_id or "").strip(),
        (venue_name or "").strip() if isinstance(venue_name, str) else "",
    )


def _match_venue(store: Store, venue_id: str, venue_name: str) -> tuple[str | None, str | None]:
    if not venue_id and not venue_name:
        return None, None
    if venue_id:
        row = store.get_venue(venue_id)
        if row is None:
            raise EventWriteError("no room with that id is on the calendar")
        if venue_name and row["name"].casefold() != venue_name.casefold():
            raise EventWriteError("venueId and venue name are different rooms")
        return row["id"], row["name"]
    rows = store.query(
        "SELECT id, name FROM venues WHERE name = ? COLLATE NOCASE",
        (venue_name,),
    )
    if not rows:
        raise EventWriteError(
            "no room by that name is on the calendar. This API does not add rooms."
        )
    if len(rows) > 1:
        raise EventWriteError("that room name matches more than one record; pass venueId")
    return rows[0]["id"], rows[0]["name"]


def _write_listing(store: Store, external_id: str, fields: dict, *, suppressed: bool) -> tuple[int, str]:
    store.upsert_source(AGENT_SOURCE, "manual", None, interval_min=0, enabled=False)
    raw = {
        "kind": fields["kind"],
        "categories": [],
        "local_date": fields["local_date"],
        "agent": True,
        "suppressed": suppressed,
    }
    listing_id, action, _diffs = store.upsert_listing(
        source_id=AGENT_SOURCE,
        external_id=external_id,
        url=fields["source_url"],
        title_raw=fields["title"],
        title_norm=fields["title_norm"],
        description=fields["description"],
        starts_at=fields["starts"].astimezone(timezone.utc).replace(microsecond=0).isoformat(),
        ends_at=(
            fields["ends"].astimezone(timezone.utc).replace(microsecond=0).isoformat()
            if fields["ends"] is not None else None
        ),
        status=fields["status"],
        venue_id=fields["venue_id"],
        venue_name_raw=fields["venue_name"] or "",
        raw_json=raw,
    )
    return listing_id, action


def _base_from(event: dict, listing) -> dict:
    if listing is not None:
        raw = _raw(listing["raw_json"])
        starts = _parsed(listing["starts_at"])
        ends = _parsed(listing["ends_at"]) if listing["ends_at"] else None
        return {
            "title": listing["title_raw"],
            "starts": starts,
            "ends": ends,
            "source_url": listing["url"] or "",
            "kind": raw.get("kind") or event.get("kind") or "other",
            "status": listing["status"] or event.get("status") or "EventScheduled",
            "description": listing["description"],
            "venue_id": listing["venue_id"],
            "venue_name": listing["venue_name_raw"] or event.get("venue") or "",
        }
    starts = _parsed(event["startsAt"]) if event.get("startsAt") else None
    if starts is None:
        raise EventWriteError("that show has no start time to correct")
    ends = _parsed(event["endsAt"]) if event.get("endsAt") else None
    return {
        "title": event["title"],
        "starts": starts,
        "ends": ends,
        "source_url": "",
        "kind": event.get("kind") or "other",
        "status": event.get("status") or "EventScheduled",
        "description": None,
        "venue_id": event.get("venueId") or None,
        "venue_name": event.get("venue") or "",
    }


def _agent_listing(store: Store, event_id: str):
    return store.one(
        """
        SELECT l.*
        FROM listings l
        JOIN event_listings el ON el.listing_id = l.id
        WHERE el.event_id = ? AND l.source_id = ?
        ORDER BY l.id
        LIMIT 1
        """,
        (event_id, AGENT_SOURCE),
    )


def _event_for_listing(store: Store, listing_id: int) -> str:
    row = store.one(
        "SELECT event_id FROM event_listings WHERE listing_id = ?",
        (listing_id,),
    )
    if row is None:
        raise EventWriteError("the show was stored but did not resolve", 500)
    return row["event_id"]


def _still_linked(store: Store, event_id: str) -> bool:
    row = store.one(
        "SELECT 1 AS ok FROM event_listings WHERE event_id = ? LIMIT 1",
        (event_id,),
    )
    return row is not None


def _set_rail(store: Store, event_id: str, value: str, reason: str) -> None:
    state = "shown"
    rows = store.query(
        """
        SELECT new_value FROM event_changes
        WHERE event_id = ? AND field = 'rail'
        ORDER BY id DESC LIMIT 1
        """,
        (event_id,),
    )
    if rows and rows[0]["new_value"]:
        state = rows[0]["new_value"]
    if state == value:
        return
    store.record_change(event_id, "rail", state, value, reason=reason)


def _mark_suppressed(store: Store, listing_id: int, suppressed: bool) -> None:
    row = store.one("SELECT raw_json FROM listings WHERE id = ?", (listing_id,))
    raw = _raw(row["raw_json"] if row else None)
    raw["suppressed"] = suppressed
    store.execute(
        "UPDATE listings SET raw_json = ? WHERE id = ?",
        (json.dumps(raw), listing_id),
    )


def _find(store: Store, event_id: str, *, include_hidden: bool) -> dict | None:
    _venues, events, _hidden = load_rows(store, include_hidden=include_hidden)
    for event in events:
        if event["id"] == event_id:
            return event
    return None


def _check_id(event_id: str) -> None:
    if not isinstance(event_id, str) or not _EVENT_ID.fullmatch(event_id):
        raise EventWriteError("no show with that id", 404)


def _follow(store: Store, event_id: str) -> str:
    """The show an id refers to now.

    A title or time change resolves to a new id. The id the agent already
    holds still works: the change log names the show it became.
    """
    _check_id(event_id)
    seen: set[str] = set()
    current = event_id
    while current not in seen:
        seen.add(current)
        if _find(store, current, include_hidden=True) is not None:
            return current
        row = store.one(
            """
            SELECT new_value FROM event_changes
            WHERE event_id = ? AND field = 'successor'
            ORDER BY id DESC LIMIT 1
            """,
            (current,),
        )
        nxt = row["new_value"] if row else ""
        if not nxt or not _EVENT_ID.fullmatch(nxt):
            break
        current = nxt
    raise EventWriteError("no show with that id", 404)


def _public_url(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EventWriteError("a show needs a public sourceUrl")
    url = value.strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        raise EventWriteError("sourceUrl has to be an http or https link")
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        raise EventWriteError("sourceUrl has to be a public page, not this machine")
    return url


def _when(body: dict, key: str, *, required: bool, allow_null: bool = False):
    if key not in body and _snake(key) not in body:
        if required:
            raise EventWriteError(f"{key} is required")
        return _UNSET
    value = body[key] if key in body else body[_snake(key)]
    if value is None and allow_null:
        return None
    if not isinstance(value, str) or not value.strip():
        raise EventWriteError(
            f"{key} has to be a date and time with a timezone, like 2026-10-09T20:00:00-07:00"
        )
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        raise EventWriteError(
            f"{key} has to be a date and time with a timezone, like 2026-10-09T20:00:00-07:00"
        ) from None
    if parsed.tzinfo is None:
        raise EventWriteError(f"{key} needs a timezone offset. Metropolis is America/Los_Angeles")
    return parsed


def _text(body: dict, key: str, *, required: bool, limit: int):
    if key not in body:
        if required:
            raise EventWriteError(f"{key} is required")
        return _UNSET
    value = body[key]
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise EventWriteError(f"{key} is required" if required else f"{key} has to be text")
    text = value.strip()
    if len(text) > limit:
        raise EventWriteError(f"{key} is too long")
    return text


def _choice(body: dict, key: str, allowed: set[str], label: str):
    if key not in body:
        return _UNSET
    value = body[key]
    if not isinstance(value, str) or value not in allowed:
        raise EventWriteError(f"{label} has to be one of: {', '.join(sorted(allowed))}")
    return value


def _touches(body: dict) -> bool:
    keys = {
        "title", "startsAt", "endsAt", "sourceUrl", "source_url",
        "kind", "status", "description", "venue", "venueId",
    }
    return any(key in body for key in keys)


def _external_id(value: object, source_url: str) -> str:
    if value is None:
        return stable_id("agent", source_url)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
        raise EventWriteError("externalId has to be a short id")
    text = value.strip()
    if any(ord(char) < 32 for char in text):
        raise EventWriteError("externalId has to be a short id")
    return text


def _parsed(value: str | None):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _raw(text: str | None) -> dict:
    try:
        raw = json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _flag(value: object) -> bool:
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "").lower() in {"1", "true", "yes"}


def _one(value: object) -> str:
    if isinstance(value, list):
        return str(value[0]).strip() if value else ""
    return str(value or "").strip()


def _snake(key: str) -> str:
    out = []
    for char in key:
        if char.isupper():
            out.append("_")
            out.append(char.lower())
        else:
            out.append(char)
    return "".join(out)
