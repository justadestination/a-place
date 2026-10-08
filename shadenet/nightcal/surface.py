"""Build the A2UI v0.9 message stream for the downtown night calendar.

The component tree is stable. What changes between fills is the data
model: rooms, shows, and whatever night the reader currently has open.
A client that already has the surface applies updateDataModel and
leaves the tree alone.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from shadenet.nightcal.closures import cite_closures, is_closed, note_for
from shadenet.nightcal.fill import AGENT_SOURCE, DAO_SOURCE, DB_PATH
from shadenet.nightcal.social import social_rank, social_status
from shadenet.nightcal.votes import vote_map
from shadenet.towncrier.store import Store

CATALOG_ID = "https://towncrier.local/catalogs/nightcal/v1/catalog.json"
SURFACE_ID = "downtown-nights"
LA = ZoneInfo("America/Los_Angeles")

NIGHT_KINDS = {"music", "comedy", "show", "trivia"}

# House preference for a host that has not set its own. Caps keep a
# preference from tipping the sheet so far that days cover each other.
HOUSE_TILT = 22
HOUSE_DEPTH = 16
HOUSE_FOCUS = 1.2
HOUSE_SUSPENDED = True
TILT_MAX = 24
DEPTH_MAX = 24
FOCUS_MAX = 1.6

_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
_WEEKDAYS = (
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
)


def _local(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed.astimezone(LA)


def _clock(moment: datetime | None) -> str:
    if moment is None:
        return ""
    hour = moment.hour % 12 or 12
    suffix = "am" if moment.hour < 12 else "pm"
    return f"{hour}:{moment.minute:02d} {suffix}"


def _month_key(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def _parse_month(value: str) -> tuple[int, int]:
    year, month = value.split("-")
    return int(year), int(month)


def _shift_month(key: str, delta: int) -> str:
    year, month = _parse_month(key)
    month += delta
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return f"{year:04d}-{month:02d}"


def _clamp_date(key: str, selected: str) -> str:
    year, month = _parse_month(key)
    try:
        current = date.fromisoformat(selected)
    except ValueError:
        current = date(year, month, 1)
    if current.year == year and current.month == month:
        return current.isoformat()
    day = min(current.day, _days_in_month(year, month))
    return date(year, month, day).isoformat()


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return (date(year + 1, 1, 1) - date(year, month, 1)).days
    return (date(year, month + 1, 1) - date(year, month, 1)).days


_SOCIAL_LABELS = (
    ("facebook.com", "Facebook"),
    ("fb.com", "Facebook"),
    ("instagram.com", "Instagram"),
    ("twitter.com", "X"),
    ("x.com", "X"),
)


def _host(value: str) -> str:
    text = value.strip()
    if "://" not in text:
        text = "//" + text
    host = text.split("//", 1)[1].split("/", 1)[0].lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _phone_href(shown: str) -> str | None:
    digits = "".join(ch for ch in shown if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return "tel:+1" + digits


def _web_href(shown: str) -> str | None:
    text = shown.strip()
    if not text or text.lower().startswith("osm:"):
        return None
    if text.startswith("http://"):
        text = "https://" + text[len("http://"):]
    if text.startswith("https://"):
        return text
    if " " in text or "@" in text:
        return None
    return "https://" + text.lstrip("/")


_SOURCE_NAMES = {
    DAO_SOURCE: "Downtown Metropolis",
    AGENT_SOURCE: "Filed",
    "facebook": "Facebook",
    "instagram": "Instagram",
    "x": "X",
}


def _source_name(source_id: str) -> str:
    if source_id in _SOURCE_NAMES:
        return _SOURCE_NAMES[source_id]
    return source_id


def _rail_contact(kind: str, source_id: str, excerpt: str, value: str) -> bool:
    """The rail shows a fact a tag, a link, or structured data stated.

    A phone-shaped number inside an Instagram id, or the placeholder
    user@domain.com, is not contact info.
    """
    source = source_id or ""
    text = excerpt or ""
    if source.startswith("osm"):
        return True
    if kind == "phone":
        if text.startswith("JSON-LD telephone") or "tel:" in text:
            return True
        lowered = text.lower()
        if any(bad in lowered for bad in ("padding", "wp-", "instagram id")):
            return False
        return bool(re.search(r"\d{3}[\s.\-)]+\d{3}[\s.\-]+\d{4}", text))
    if kind == "email":
        if text.startswith("JSON-LD email") or "mailto:" in text:
            return True
        lowered = (value or "").lower()
        if any(bad in lowered for bad in ("user@", "example.com", "domain.com", "email@")):
            return False
        return "email" in text.lower()
    if kind == "website":
        return text.startswith("JSON-LD url")
    if kind == "social":
        return text.startswith("JSON-LD sameAs") or text.startswith("href=") or text.startswith("OSM ")
    return False


def contact_for(store: Store, entity_id: str | None) -> dict:
    """Cited phone, mail, site, and social links. The osm: identity row is not a profile."""
    found = {"phones": [], "emails": [], "websites": [], "socials": []}
    if not entity_id:
        return found
    rows = store.query(
        """
        SELECT i.kind, i.value, i.display, c.source_id AS cite_source, c.excerpt
        FROM items i
        LEFT JOIN citations c ON c.item_id = i.id
        WHERE i.entity_id = ? AND i.kind IN ('phone', 'email', 'website', 'social')
        ORDER BY i.confidence DESC, i.id
        """,
        (entity_id,),
    )
    ordered = []
    grouped: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["kind"], row["value"] or "")
        item = grouped.get(key)
        if item is None:
            item = {"kind": row["kind"], "value": row["value"], "display": row["display"], "ok": False}
            grouped[key] = item
            ordered.append(item)
        if _rail_contact(row["kind"], row["cite_source"] or "", row["excerpt"] or "", row["value"] or ""):
            item["ok"] = True
    seen: set[tuple[str, str]] = set()
    for row in ordered:
        if not row["ok"]:
            continue
        kind = row["kind"]
        value = (row["value"] or "").strip()
        shown = (row["display"] or value).strip()
        if not shown or value.lower().startswith("osm:") or shown.lower().startswith("osm:"):
            continue
        if kind == "phone":
            href = _phone_href(shown)
            key = ("phone", href or shown)
            if key in seen:
                continue
            seen.add(key)
            found["phones"].append({"text": shown, "href": href or ""})
        elif kind == "email":
            if "@" not in shown:
                continue
            href = "mailto:" + shown.split()[0]
            if ("email", href) in seen:
                continue
            seen.add(("email", href))
            found["emails"].append({"text": shown.split()[0], "href": href})
        elif kind == "website":
            href = _web_href(shown)
            if not href:
                continue
            label = href.split("://", 1)[-1].strip("/")
            if ("website", href) in seen:
                continue
            seen.add(("website", href))
            found["websites"].append({"text": label, "href": href})
        elif kind == "social":
            href = _web_href(shown) or _web_href(row["value"] or "")
            if not href:
                continue
            lowered = href.lower()
            if any(bit in lowered for bit in ("/sharer", "/share.php", "/intent/", "/dialog/")):
                continue
            host = _host(href)
            label = next((name for domain, name in _SOCIAL_LABELS if host == domain or host.endswith("." + domain)), "")
            if not label:
                continue
            if ("social", href) in seen:
                continue
            seen.add(("social", href))
            current = next((item for item in found["socials"] if item["text"] == label), None)
            if current is None:
                found["socials"].append({"text": label, "href": href})
            elif social_rank(href) < social_rank(current["href"]):
                current["href"] = href
    found["websites"] = _home_sites(found["websites"])
    return found


def _home_sites(sites: list[dict]) -> list[dict]:
    """One site per host, the shortest path. A logo or a nav page is not the site."""
    kept: dict[str, tuple[int, dict]] = {}
    for site in sites:
        href = site.get("href") or ""
        tail = href.split("://", 1)[-1]
        host, _, path = tail.partition("/")
        path = "/" + path.split("?", 1)[0].split("#", 1)[0]
        lowered = path.lower()
        if "/wp-content/" in lowered or lowered.rstrip("/").endswith(
            (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf")
        ):
            continue
        rank = len(path.rstrip("/") or "/")
        current = kept.get(host)
        if current is None or rank < current[0]:
            kept[host] = (rank, site)
    return [item[1] for item in kept.values()]


def _raw_obj(text: str | None) -> dict:
    try:
        raw = json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def rail_hidden(store: Store) -> set[str]:
    """Event ids an agent took off the sheet.

    The flag lives in the change log, not on the listing. A calendar
    reread rewrites downtown listings and re-resolves, and both of those
    leave event_changes alone, so a removal survives the next fill.
    """
    state: dict[str, str] = {}
    for row in store.query(
        "SELECT event_id, new_value FROM event_changes WHERE field = 'rail' ORDER BY id"
    ):
        state[row["event_id"]] = row["new_value"] or ""
    return {event_id for event_id, value in state.items() if value == "hidden"}


def load_rows(store: Store, *, include_hidden: bool = False) -> tuple[list[dict], list[dict], list[str]]:
    cite_closures(store)
    votes = vote_map(store)
    venues = []
    for row in store.query("SELECT * FROM venues ORDER BY name"):
        handles = {}
        try:
            handles = json.loads(row["handles"] or "{}")
        except json.JSONDecodeError:
            handles = {}
        entity = store.one(
            "SELECT id, meta FROM entities WHERE kind = 'venue' AND name = ?",
            (row["name"],),
        )
        meta = {}
        if entity and entity["meta"]:
            try:
                meta = json.loads(entity["meta"])
            except json.JSONDecodeError:
                meta = {}
        music = bool(handles.get("music") or meta.get("music"))
        entity_id = handles.get("entity_id") or (entity["id"] if entity else "")
        venues.append({
            "id": row["id"],
            "name": row["name"],
            "music": music,
            "contact": contact_for(store, entity_id),
            "amenity": meta.get("amenity") or handles.get("amenity") or "",
            "address": row["address"] or "",
            "lat": row["lat"],
            "lon": row["lon"],
            "score": meta.get("score") or 0,
            "reasons": meta.get("reasons") or [],
            "osm": bool(meta.get("osm_id")),
        })

    events = []
    hidden_ids = rail_hidden(store)
    rows = store.query(
        """
        SELECT e.id, e.title, e.starts_at, e.ends_at, e.status, e.venue_id,
               e.confidence, e.needs_review, e.source_count, e.ticket_url,
               e.image_url, e.active,
               v.name AS venue_name,
               l.url AS listing_url, l.source_id, l.raw_json, l.venue_name_raw, l.description,
               l.title_raw AS listing_title, l.starts_at AS listing_starts, l.ends_at AS listing_ends
        FROM events e
        JOIN event_listings el ON el.event_id = e.id
        JOIN listings l ON l.id = el.listing_id
        LEFT JOIN venues v ON v.id = e.venue_id
        WHERE e.active = 1
        ORDER BY e.starts_at, e.title, l.id
        """
    )
    grouped: dict[str, dict] = {}
    order: list[str] = []
    for row in rows:
        bucket = grouped.get(row["id"])
        if bucket is None:
            bucket = {"row": row, "listings": []}
            grouped[row["id"]] = bucket
            order.append(row["id"])
        bucket["listings"].append(row)
        if row["source_id"] == DAO_SOURCE and bucket["row"]["source_id"] != DAO_SOURCE:
            bucket["row"] = row
    for event_id in order:
        listings = grouped[event_id]["listings"]
        # A filed correction is what the sheet shows. The downtown listing
        # stays underneath it and is linked as a check, not overwritten.
        agent = next(
            (
                item for item in listings
                if item["source_id"] == AGENT_SOURCE and not _raw_obj(item["raw_json"]).get("suppressed")
            ),
            None,
        )
        row = agent or grouped[event_id]["row"]
        taken_down = event_id in hidden_ids or all(
            _raw_obj(item["raw_json"]).get("suppressed") for item in listings
        )
        if taken_down and not include_hidden:
            continue
        ups = downs = 0
        for listing in listings:
            vote_up, vote_down = votes.get(listing["listing_url"] or "", (0, 0))
            if abs(vote_up - vote_down) > abs(ups - downs) or (ups == 0 and downs == 0 and (vote_up or vote_down)):
                ups, downs = vote_up, vote_down
        raw = _raw_obj(row["raw_json"])
        start = _local(row["starts_at"])
        end = _local(row["ends_at"])
        title = row["title"]
        starts_at = row["starts_at"] or ""
        ends_at = row["ends_at"] or ""
        if row["source_id"] == AGENT_SOURCE:
            title = row["listing_title"] or title
            start = _local(row["listing_starts"]) or start
            starts_at = row["listing_starts"] or starts_at
            if row["listing_ends"]:
                end = _local(row["listing_ends"])
                ends_at = row["listing_ends"]
        local_date = raw.get("local_date") or (start.date().isoformat() if start else "")
        checks = []
        seen_urls = {row["listing_url"] or ""}
        for listing in listings:
            url = listing["listing_url"] or ""
            if listing["source_id"] == row["source_id"] or not url.startswith("https://") or url in seen_urls:
                continue
            seen_urls.add(url)
            checks.append({"name": _source_name(listing["source_id"] or ""), "url": url})
        performers = [
            {"name": p["name"], "billing": p["billing"]}
            for p in store.query(
                """
                SELECT p.name, ep.billing
                FROM event_performers ep
                JOIN performers p ON p.id = ep.performer_id
                WHERE ep.event_id = ?
                ORDER BY CASE ep.billing WHEN 'headline' THEN 0
                                         WHEN 'support' THEN 1 ELSE 2 END,
                         p.name
                """,
                (row["id"],),
            )
        ]
        events.append({
            "id": row["id"],
            "title": title,
            "startsAt": starts_at,
            "endsAt": ends_at,
            "suppressed": taken_down,
            "venue": row["venue_name"] or row["venue_name_raw"] or "",
            "venueId": row["venue_id"] or "",
            "date": local_date,
            "startLabel": _clock(start),
            "endLabel": _clock(end),
            "kind": raw.get("kind") or "other",
            "categories": raw.get("categories") or [],
            "status": row["status"],
            "sourceUrl": row["listing_url"] or "",
            "sourceName": _source_name(row["source_id"] or ""),
            "checks": checks,
            "image": row["image_url"] or raw.get("image") or "",
            "performers": performers,
            "confidence": row["confidence"],
            "needsReview": bool(row["needs_review"]),
            "sourceCount": row["source_count"],
            "minutes": (start.hour * 60 + start.minute) if start else 24 * 60,
            "up": ups,
            "down": downs,
            "score": ups - downs,
        })
    on_sheet = [event for event in events if not event.get("suppressed")]
    music_rooms = {event["venueId"] for event in on_sheet if event["kind"] == "music" and event["venueId"]}
    booked = {event["venueId"] for event in on_sheet if event["venueId"]}
    for venue in venues:
        if venue["id"] in music_rooms:
            venue["music"] = True
    # A closed room with a cited show still stays. The listing is the
    # evidence that something is happening there, and it outranks the notice.
    hidden = []
    open_rooms = []
    for venue in venues:
        if is_closed(venue["name"]) and venue["id"] not in booked:
            hidden.append(venue["name"])
            continue
        open_rooms.append(venue)
    return open_rooms, events, hidden


def visible(events: list[dict], ui: dict) -> list[dict]:
    venue_id = ui.get("venueId") or ""
    scope = ui.get("scope") or "nights"
    chosen = []
    for event in events:
        if venue_id and event["venueId"] != venue_id:
            continue
        if scope == "nights" and event["kind"] not in NIGHT_KINDS:
            continue
        chosen.append(event)
    return chosen


def _bounded(raw: dict, key: str, default: float, lo: float, hi: float) -> float:
    try:
        value = float(raw.get(key, default))
    except (TypeError, ValueError):
        value = float(default)
    if value != value:  # NaN
        value = float(default)
    value = min(hi, max(lo, round(value, 2)))
    if value == int(value):
        return int(value)
    return value


def _flag(raw: dict, key: str, default: bool) -> bool:
    if key not in raw:
        return default
    value = raw[key]
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def clamp_view(raw: object) -> dict:
    """Host preference for the sheet. Missing fields use the house defaults."""
    if not isinstance(raw, dict):
        raw = {}
    return {
        "tilt": _bounded(raw, "tilt", HOUSE_TILT, 0, TILT_MAX),
        "depth": _bounded(raw, "depth", HOUSE_DEPTH, 0, DEPTH_MAX),
        "bars": _flag(raw, "bars", True),
        "focus": _bounded(raw, "focus", HOUSE_FOCUS, 1, FOCUS_MAX),
        "suspended": _flag(raw, "suspended", HOUSE_SUSPENDED),
    }


def depth_note(view: dict) -> str:
    if view["tilt"] <= 0:
        sentence = "The sheet lies flat."
    elif view.get("suspended"):
        sentence = "The month hangs open, and the sheet tips forward."
    else:
        sentence = "The sheet tips forward."
    if view["bars"] and view["depth"] > 0:
        relation = (
            "Each bar, and how close the show sits, is that night against "
            "the strongest night on this sheet."
        )
    elif view["bars"]:
        relation = "Each bar is that night against the strongest night on this sheet."
    elif view["depth"] > 0:
        relation = (
            "How close a show sits is that night against the strongest night on this sheet."
        )
    else:
        relation = ""
    # A flat sheet has no forward lift, and the note stays the one flat sentence.
    space = ""
    if view["tilt"] > 0:
        space = (
            "On an open day, left to right is the hour, top to bottom is the room, "
            "and the wire is how long the set runs."
        )
    return " ".join(part for part in (sentence, relation, space) if part)


def default_ui(today: date | None = None) -> dict:
    today = today or datetime.now(LA).date()
    return {
        "month": _month_key(today),
        "selectedDate": today.isoformat(),
        "venueId": "",
        "scope": "nights",
        "view": clamp_view(None),
    }


def apply_action(ui: dict, name: str, context: dict | None) -> dict:
    context = context or {}
    ui = dict(ui)
    if name == "selectDate" and context.get("date"):
        ui["selectedDate"] = str(context["date"])
        ui["month"] = ui["selectedDate"][:7]
    elif name == "shiftMonth":
        delta = int(context.get("delta") or 0)
        ui["month"] = _shift_month(ui["month"], delta)
        ui["selectedDate"] = _clamp_date(ui["month"], ui["selectedDate"])
    elif name == "filterVenue":
        requested = str(context.get("venueId") or "")
        ui["venueId"] = "" if requested == ui.get("venueId") else requested
    elif name == "setScope":
        scope = str(context.get("scope") or "nights")
        ui["scope"] = scope if scope in ("nights", "all") else "nights"
    return ui


def project(venues: list[dict], events: list[dict], ui: dict, *, status: str = "", hidden: list[str] | None = None) -> dict:
    shown = visible(events, ui)
    year, month = _parse_month(ui["month"])
    selected = _clamp_date(ui["month"], ui["selectedDate"])
    bill = [event for event in shown if event["date"] == selected]
    bill.sort(key=lambda event: (event.get("minutes", 0), event["title"]))
    try:
        selected_day = date.fromisoformat(selected)
        date_label = f"{_WEEKDAYS[selected_day.weekday()]}, {_MONTHS[selected_day.month - 1]} {selected_day.day}"
    except ValueError:
        date_label = selected
    nights = sum(1 for event in shown if event["kind"] in NIGHT_KINDS)
    scope = ui.get("scope") or "nights"
    room_count = sum(1 for venue in venues if venue["osm"])
    view = clamp_view(ui.get("view"))
    return {
        "place": "Downtown Metropolis",
        "venues": sorted(venues, key=lambda venue: (not venue["music"], venue["name"].lower())),
        "events": events,
        "ui": {
            "month": ui["month"],
            "monthLabel": f"{_MONTHS[month - 1]} {year}",
            "selectedDate": selected,
            "dateLabel": date_label,
            "venueId": ui.get("venueId") or "",
            "scope": scope,
            "showsVariant": "primary" if scope == "nights" else "borderless",
            "allVariant": "primary" if scope == "all" else "borderless",
            "showCount": f"{nights} shows" if scope == "nights" else f"{len(shown)} listings",
            "roomCount": room_count,
            "bill": bill,
            "status": status,
            "view": view,
            "closedNote": note_for(hidden or []),
            "depthNote": depth_note(view),
            "attribution": (
                "Rooms from OpenStreetMap contributors. "
                "Shows from the Downtown Metropolis calendar. "
                "A Facebook, Instagram, or X page is cited only when that page itself lists the show."
            ),
        },
    }


def components() -> list[dict]:
    return [
        {"id": "root", "component": "Column", "children": [
            "marquee", "controls", "rail", "depth-note", "cal", "closed-note", "footer",
        ]},
        {"id": "marquee", "component": "Marquee",
         "place": {"path": "/place"},
         "month": {"path": "/ui/monthLabel"},
         "count": {"path": "/ui/showCount"},
         "status": {"path": "/ui/status"}},
        {"id": "controls", "component": "Row", "children": [
            "scope-shows", "scope-all", "prev", "next", "refresh",
        ], "justify": "start", "align": "center"},
        {"id": "scope-shows-label", "component": "Text", "text": "Shows"},
        {"id": "scope-shows", "component": "Button", "child": "scope-shows-label",
         "variant": {"path": "/ui/showsVariant"},
         "action": {"event": {"name": "setScope", "context": {"scope": "nights"}}}},
        {"id": "scope-all-label", "component": "Text", "text": "All listings"},
        {"id": "scope-all", "component": "Button", "child": "scope-all-label",
         "variant": {"path": "/ui/allVariant"},
         "action": {"event": {"name": "setScope", "context": {"scope": "all"}}}},
        {"id": "prev-label", "component": "Text", "text": "Previous month"},
        {"id": "prev", "component": "Button", "child": "prev-label", "variant": "borderless",
         "action": {"event": {"name": "shiftMonth", "context": {"delta": -1}}}},
        {"id": "next-label", "component": "Text", "text": "Next month"},
        {"id": "next", "component": "Button", "child": "next-label", "variant": "borderless",
         "action": {"event": {"name": "shiftMonth", "context": {"delta": 1}}}},
        {"id": "refresh-label", "component": "Text", "text": "Check for new listings"},
        {"id": "refresh", "component": "Button", "child": "refresh-label", "variant": "borderless",
         "action": {"event": {"name": "refresh"}}},
        {"id": "depth-note", "component": "Text", "variant": "caption",
         "text": {"path": "/ui/depthNote"}},
        {"id": "rail", "component": "VenueRail",
         "venues": {"path": "/venues"},
         "selected": {"path": "/ui/venueId"},
         "action": {"event": {"name": "filterVenue"}}},
        {"id": "cal", "component": "NightCalendar",
         "month": {"path": "/ui/month"},
         "selectedDate": {"path": "/ui/selectedDate"},
         "events": {"path": "/events"},
         "venueId": {"path": "/ui/venueId"},
         "scope": {"path": "/ui/scope"},
         "view": {"path": "/ui/view"},
         "action": {"event": {"name": "selectDate"}},
         "vote": {"event": {"name": "vote"}}},
        {"id": "closed-note", "component": "Text", "variant": "caption",
         "text": {"path": "/ui/closedNote"}},
        {"id": "footer", "component": "Text", "variant": "caption",
         "text": {"path": "/ui/attribution"}},
    ]


def create_surface_message() -> dict:
    return {
        "version": "v0.9",
        "createSurface": {
            "surfaceId": SURFACE_ID,
            "catalogId": CATALOG_ID,
            "theme": {
                "primaryColor": "#FFC14D",
                "background": "#12161A",
                "foreground": "#D7E3E4",
                "sheet": "#D7E3E4",
                "ink": "#172326",
            },
            "sendDataModel": False,
        },
    }


def update_components_message() -> dict:
    return {
        "version": "v0.9",
        "updateComponents": {
            "surfaceId": SURFACE_ID,
            "components": components(),
        },
    }


def update_data_message(model: dict) -> dict:
    return {
        "version": "v0.9",
        "updateDataModel": {
            "surfaceId": SURFACE_ID,
            "path": "/",
            "value": model,
        },
    }


def messages_for(store: Store, ui: dict, *, status: str = "") -> list[dict]:
    venues, events, hidden = load_rows(store)
    model = project(venues, events, ui, status=status or social_status(store), hidden=hidden)
    return [
        create_surface_message(),
        update_components_message(),
        update_data_message(model),
    ]


def dumps(messages: list[dict]) -> str:
    return "".join(json.dumps(message, ensure_ascii=False) + "\n" for message in messages)


def open_store(db_path: Path | None = None) -> Store:
    return Store(db_path or DB_PATH)
