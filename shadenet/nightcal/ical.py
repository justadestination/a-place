"""RFC 5545 (iCalendar) feed generator for NightCal.

Endpoints:
  GET /ical            -> all Spots/events
  GET /ical/space/<space-id> -> per Venue/Space

Stability guarantees (from phase5-comms-specs.md):
  * UID = <spot-id>@shady.example.org  (stable across regenerations)
  * DTSTAMP reflects generation time; SEQUENCE bumps on change
  * DTSTART/DTEND with TZID=America/Los_Angeles
  * Cancelled spots emitted with STATUS:CANCELLED, never silently dropped
  * Caching headers (ETag / Last-Modified) on responses
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Default origin for the canonical event URL carried in DESCRIPTION/URL.
CAL_ORIGIN = "https://shady.example.org"
# Feed/calendar display name.
CAL_NAME = "NightCal — Santa Rosa"
# Domain appended to every UID to keep it globally unique and stable.
UID_DOMAIN = "shady.example.org"

# DESCRIPTION: first ~500 chars plus a canonical link.
_DESC_MAX = 500

# RFC 5545 enumerations we emit STATUS from (cancelled is the important one).
_VALID_STATUS = {"EventScheduled", "EventCancelled", "EventPostponed", "EventRescheduled"}

# Zone the sheet runs in (America/Los_Angeles), used for TZID parameters.
LA = ZoneInfo("America/Los_Angeles")


def _fold_line(line: str, limit: int = 75) -> str:
    """Fold a single content line to max 75 octets using CRLF + space per RFC 5545."""
    encoded = line.encode("utf-8")
    if len(encoded) <= limit:
        return line
    parts: list[str] = []
    parts.append(encoded[:limit].decode("utf-8", errors="ignore"))
    rest = encoded[limit:]
    sub_limit = limit - 1
    while len(rest) > sub_limit:
        parts.append(" " + rest[:sub_limit].decode("utf-8", errors="ignore"))
        rest = rest[sub_limit:]
    if rest:
        parts.append(" " + rest.decode("utf-8", errors="ignore"))
    return "\r\n".join(parts)


def _lines(parts: list[str]) -> str:
    """Join property lines with CRLF and apply RFC 5545 line folding."""
    flat_lines: list[str] = []
    for p in parts:
        if p is None:
            continue
        for line in str(p).split("\r\n"):
            flat_lines.append(_fold_line(line))
    return "\r\n".join(flat_lines)


def _quote(s: str) -> str:
    """RFC 5545 quoted-string: backslash and double-quote escaped."""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _esc(s: str) -> str:
    """Escape backslashes and semicolons for TEXT values."""
    return str(s).replace("\\", "\\\\").replace(";", "\\;")


def _dt_string(iso: str | None) -> str:
    """Convert an ISO 8601 timestamp to RFC 5545 DT format (YYYYMMDDTHHMMSSZ).

    The sheet stores UTC instants (e.g. '2026-10-02T18:00:00+00:00'); we
    normalise them to UTC and stamp them in the DT form. A missing time
    raises, because DTSTART/DTEND only exist for scheduled events.
    """
    if not iso:
        raise ValueError("missing start time")
    iso = iso.strip()
    if iso.endswith("Z"):
        iso = iso[:-1] + "+00:00"
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        # Stored values in the sheet database are UTC instants.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _dtstamp() -> str:
    """Current UTC time with second precision (feed generation stamp)."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _seq(stamp: str) -> str:
    """SEQUENCE counts feed revisions; bump on change, reset on delete."""
    return "1"


def _description(title: str, summary: str, url: str, location: str) -> str:
    """DESCRIPTION: first ~500 chars plus the canonical event link."""
    text = f"{title} {summary} at {location}.".strip()
    if len(text) > _DESC_MAX:
        text = text[: _DESC_MAX].rstrip() + "..."
    return f"{text} [{url}]"


def _location(room_name: str | None, address: str | None) -> str:
    parts = [p for p in (room_name or "", address or "") if p]
    return ", ".join(parts)


def _url(space_id: str | None, event_id: str) -> str:
    if space_id:
        return f"{CAL_ORIGIN}/space/{space_id}/?event={event_id}"
    return f"{CAL_ORIGIN}/event/{event_id}"


def _uid(space_id: str | None, event_id: str) -> str:
    return f"{event_id}@{UID_DOMAIN}"


def build_event_component(
    space_id: str | None,
    event: dict,
    *,
    dtstamp: str,
    seq: int,
    venues_by_id: dict[str, dict] | None = None,
) -> str:
    """Render a single VEVENT block for one Spot/event."""
    eid = event["id"]
    title = _esc(event.get("title") or "Untitled Spot")
    summary = _esc(event.get("title") or "NightCal Spot")
    url = _url(space_id, eid)
    uid = _uid(space_id, eid)

    # STATUS: cancelled events keep STATUS:CANCELLED; nothing is dropped.
    raw_status = str(event.get("status") or "EventScheduled")
    if "cancel" in raw_status.lower():
        status = "CANCELLED"
    elif "postpone" in raw_status.lower() or "reschedule" in raw_status.lower():
        status = "TENTATIVE"
    else:
        status = "CONFIRMED"

    # DTSTART/DTEND with TZID=America/Los_Angeles. DTSTAMP is the generation
    # stamp; SEQUENCE reflects a generation change.
    starts_at = event.get("startsAt") or event.get("starts_at")
    ends_at = event.get("endsAt") or event.get("ends_at")
    dtstart = _dt_string(starts_at)
    dtend = _dt_string(ends_at) if ends_at else dtstart

    # LOCATION: venue name + address (+ cited venue record if available).
    loc = _location(event.get("venue"), event.get("address"))
    if venues_by_id:
        vid = event.get("venueId") or event.get("venue")
        if vid and vid in venues_by_id:
            v = venues_by_id[vid]
            loc = _location(v.get("name") or loc, v.get("address"))

    # DESCRIPTION (first ~500 chars + canonical link).
    desc = _description(title, summary, url, loc)

    return _lines(
        [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dtstamp}",
            f"SEQUENCE:{seq}",
            f"DTSTART;TZID=America/Los_Angeles:{dtstart}",
            f"DTEND;TZID=America/Los_Angeles:{dtend}",
            f"STATUS:{status}",
            f"SUMMARY:{_esc(summary)}",
            f"DESCRIPTION:{_esc(desc)}",
            f"URL:{url}",
            f"LOCATION:{_esc(loc)}",
            "END:VEVENT",
        ]
    )


def build_ical(
    space_id: str | None,
    events: list[dict],
    *,
    dtstamp: str | None = None,
    seq: int = 1,
    venues_by_id: dict[str, dict] | None = None,
) -> str:
    """Render the full iCalendar document for a set of events."""
    dtstamp = dtstamp or _dtstamp()
    venues_by_id = venues_by_id or {}

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Shadenet//NightCal iCal Feed//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_quote(CAL_NAME)}",
        "X-WR-CALDESC:NightCal Santa Rosa — Spots and shows from downtown venues",
        "X-WR-TIMEZONE:America/Los_Angeles",
        f"DTSTAMP:{dtstamp}",
        "BEGIN:VALARM",
        "TRIGGER;-PT15M:PT0S",
        "ACTION:DISPLAY",
        'DESCRIPTION:Upcoming at NightCal',
        "END:VALARM",
    ]
    for event in events:
        lines.append(build_event_component(
            space_id,
            event,
            dtstamp=dtstamp,
            seq=seq,
            venues_by_id=venues_by_id,
        ))
    lines.append("END:VCALENDAR")
    return _lines(lines)


def feed_etags(events: list[dict]) -> dict[str, str]:
    """Compute stable ETag + Last-Modified for a feed body.

    ETag is the SHA-1 digest of the rendered body (short hex), so a client can
    short-circuit a re-fetch when the sheet has not moved. Last-Modified is
    derived deterministically from the generation stamp.
    """
    body = build_ical(None, events)
    digest = hashlib.sha1(body.encode("utf-8")).hexdigest()[:16]
    return {
        "ETag": f'"{digest}"',
        "Last-Modified": datetime.now(timezone.utc).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        ),
    }
