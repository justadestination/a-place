"""Fill the towncrier store with downtown Metropolis rooms and shows.

Public sources, each cited:

* OpenStreetMap, for the rooms and the contact tags the map already has.
  This is the gazetteer Hermes settled on after measuring Google Places as
  unusable for a database (the Maps Platform terms forbid storing Places
  content as a system of record). The bounding box is downtown only:
  Railroad Square through Courthouse Square to Main Street Tavern. The same
  music-signal classifier as discover.py decides which rooms look like
  they book bands.

* The Downtown Metropolis events calendar, for the dated listings.
  Each card becomes one listing. Resolution into events is towncrier's
  own Resolver, so a show that shows up twice still clusters.

* A room's own website, for phone, mail, and profile links the page states.

* A public Facebook, Instagram, or X page, only when that page itself
  lists a schema.org Event. A login wall adds nothing.

Run from the repo root:

    python3 -m nightcal.fill
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shadenet.nightcal.parse_dao import DAO_ORIGIN, acts_from_title, parse_cards
from shadenet.nightcal.social import enrich_sites, probe_social, social_url
from towncrier import discover
from shadenet.towncrier.entities import (
    KIND_ADDRESS,
    KIND_EMAIL,
    KIND_PHONE,
    KIND_SOCIAL,
    KIND_WEBSITE,
    add_item,
    ensure_entity,
    link,
)
from shadenet.towncrier.normalize import normalize_title, to_utc
from shadenet.towncrier.resolve import Resolver
from shadenet.towncrier.store import Store

DB_PATH = ROOT / "data" / "shadenet.db"
CALENDAR_URL = DAO_ORIGIN + "/events/calendar"
OSM_SOURCE = "osm"
DAO_SOURCE = "downtown_santa_rosa"
AGENT_SOURCE = "agent"

# south, west, north, east. Downtown, not the whole city: Railroad Square
# (west) to Metropolis Avenue (east), around 1st Street up to College Ave.
DOWNTOWN_BBOX = (38.428, -122.736, 38.454, -122.698)

def _downtown_query(bbox: tuple[float, float, float, float]) -> str:
    """One Overpass union, bbox on every statement.

    discover.discover_area appends the bbox after the union, which Overpass
    rejects with HTTP 400. The statements below are the same tags Hermes
    measured, plus brewery, because that is how this downtown tags the rooms
    that book bands.
    """
    south, west, north, east = bbox
    box = f"({south:.5f},{west:.5f},{north:.5f},{east:.5f})"
    filters = [
        'nwr["amenity"~"^(music|nightclub|concert_hall|events_venue|casino|public_hall|theatre|arts_centre|bar|pub|brewery|biergarten)$"]',
        'nwr["leisure"="live_music_venue"]',
        'nwr["music:type"]',
        'nwr["theatre"="live"]',
        # The map names this Railroad Square room and stops at building=commercial,
        # so the amenity filter never sees it. The name is the tag OSM already has.
        'nwr["name"="The Commons Arts Center"]["building"]',
    ]
    body = "\n".join(f"  {item}{box};" for item in filters)
    return f"[out:json][timeout:30];\n(\n{body}\n);\nout tags center;"

LA = ZoneInfo("America/Los_Angeles")
UTC = ZoneInfo("UTC")


def _iso(day: date, clock: tuple[int, int] | None) -> str | None:
    if clock is None:
        return None
    return to_utc(day, clock, "America/Los_Angeles").replace(microsecond=0).isoformat()


_SOCIAL_KEYS = (
    ("contact:facebook", "facebook"),
    ("facebook", "facebook"),
    ("contact:instagram", "instagram"),
    ("instagram", "instagram"),
    ("contact:twitter", "twitter"),
    ("twitter", "twitter"),
    ("contact:x", "twitter"),
)


def record_osm_contact(store: Store, entity_id: str, tags: dict, source_id: str, osm_url: str) -> None:
    """Write the contact tags OSM actually has. Missing tags stay missing."""
    email = (tags.get("email") or tags.get("contact:email") or "").strip()
    if "@" in email:
        add_item(
            store, entity_id=entity_id, kind=KIND_EMAIL, value=email,
            source_id=source_id, source_url=osm_url, citation_kind="html",
            excerpt="OSM email",
        )
    seen: set[str] = set()
    for key, network in _SOCIAL_KEYS:
        url = social_url(network, tags.get(key) or "")
        if not url or url in seen:
            continue
        seen.add(url)
        add_item(
            store, entity_id=entity_id, kind=KIND_SOCIAL, value=url, display=url,
            source_id=source_id, source_url=osm_url, citation_kind="html",
            excerpt=f"OSM {key}",
        )


def _address(tags: dict) -> str:
    number = tags.get("addr:housenumber") or ""
    street = tags.get("addr:street") or ""
    line = f"{number} {street}".strip()
    city = tags.get("addr:city")
    if line and city:
        return f"{line}, {city}"
    return line


def ingest_rooms(store: Store, city_id: str) -> tuple[int, list[str]]:
    """Write downtown rooms onto the trunk. Returns (count, tile failures)."""
    # Skip the mirror whose certificate does not match its hostname.
    client = discover.OverpassClient(
        cache_dir=ROOT / ".cache" / "overpass",
        endpoints=(
            "https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
        ),
        timeout_sec=40,
        max_retries=1,
        min_interval_sec=0.5,
    )
    query = _downtown_query(DOWNTOWN_BBOX)
    try:
        data = client.fetch(query)
    except discover.OverpassError as exc:
        return 0, [str(exc)]
    candidates = []
    for element in data.get("elements", []):
        tags = element.get("tags") or {}
        name = tags.get("name")
        if not name:
            continue
        lat = element.get("lat") or (element.get("center") or {}).get("lat")
        lon = element.get("lon") or (element.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        verdict, score, reasons = discover._classify(tags)
        amenity = tags.get("amenity", "")
        if amenity in ("brewery", "biergarten") and "amenity=brewery" not in " ".join(reasons):
            reasons = list(reasons) + [f"amenity={amenity}"]
        candidates.append(discover.Candidate(
            name=name,
            osm_type=element.get("type", "node"),
            osm_id=int(element.get("id", 0)),
            lat=float(lat),
            lon=float(lon),
            tags=tags,
            tile="downtown",
            is_music_venue=verdict,
            score=score,
            reasons=reasons,
        ))
    failures = []
    written = 0
    for candidate in candidates:
        tags = candidate.tags
        amenity = tags.get("amenity", "")
        # A brewery is a room worth knowing about. It is not, by itself,
        # evidence the room books bands — that still comes from the
        # music-signal classifier Hermes measured.
        music = bool(candidate.is_music_venue)
        meta = {
            "osm_type": candidate.osm_type,
            "osm_id": candidate.osm_id,
            "lat": candidate.lat,
            "lon": candidate.lon,
            "score": candidate.score,
            "reasons": candidate.reasons,
            "amenity": amenity,
            "music": music,
            "downtown": True,
        }
        entity_id = ensure_entity(
            store, name=candidate.name, kind="venue", parent_id=city_id, role="host",
            meta=meta,
        )
        store.execute(
            "UPDATE entities SET meta = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(meta), entity_id),
        )
        venue_id = store.ensure_venue(
            candidate.name,
            address=_address(tags) or None,
            city="Metropolis",
            state="CA",
            lat=candidate.lat,
            lon=candidate.lon,
            website=tags.get("website") or tags.get("contact:website"),
        )
        store.execute(
            "UPDATE venues SET handles = ? WHERE id = ?",
            (json.dumps({"entity_id": entity_id, "music": music, "amenity": amenity}), venue_id),
        )
        osm_url = candidate.osm_url
        source_id = f"osm:{candidate.osm_type}/{candidate.osm_id}"
        add_item(
            store, entity_id=entity_id, kind=KIND_SOCIAL,
            value=f"osm:{candidate.osm_type}/{candidate.osm_id}",
            display=candidate.name, source_id=source_id, source_url=osm_url,
            citation_kind="html", excerpt=amenity or "venue",
        )
        address = _address(tags)
        if address:
            add_item(
                store, entity_id=entity_id, kind=KIND_ADDRESS, value=address,
                source_id=source_id, source_url=osm_url, citation_kind="html",
            )
        phone = tags.get("phone") or tags.get("contact:phone")
        if phone:
            try:
                add_item(
                    store, entity_id=entity_id, kind=KIND_PHONE, value=phone,
                    display=phone, source_id=source_id, source_url=osm_url,
                    citation_kind="html",
                )
            except ValueError:
                pass
        website = tags.get("website") or tags.get("contact:website") or tags.get("url")
        if website:
            add_item(
                store, entity_id=entity_id, kind=KIND_WEBSITE, value=website,
                source_id=source_id, source_url=osm_url, citation_kind="html",
            )
        record_osm_contact(store, entity_id, tags, source_id, osm_url)
        written += 1
    return written, failures


def fetch_calendar(url: str = CALENDAR_URL) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": discover.USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def ingest_shows(store: Store, city_id: str, page: str, today: date | None = None) -> dict:
    """Turn calendar cards into listings, then let Resolver cluster them."""
    cards = parse_cards(page, today=today)
    seen: set[str] = set()
    new = changed = unchanged = 0
    for card in cards:
        # A card with no room stays a cited listing. "Downtown Metropolis"
        # is the place, not a venue, and inventing it put a city in the rail.
        venue_name = (card["venue"] or "").strip()
        venue_id = None
        if venue_name:
            venue_id = store.ensure_venue(venue_name, city="Metropolis", state="CA")
            # The venue record can exist with no item. The listing below is the
            # cited fact; stuffing each show URL in as a "website" would make
            # one room look like it had a dozen conflicting sites.
            ensure_entity(
                store, name=venue_name, kind="venue", parent_id=city_id, role="host",
            )
        external_id = f"{card['path']}|{card['start_date'].isoformat()}|{card['time_raw']}"
        seen.add(external_id)
        raw = {
            "kind": card["kind"],
            "categories": card["categories"],
            "time_raw": card["time_raw"],
            "local_date": card["start_date"].isoformat(),
            "image": card["image"],
        }
        _listing_id, action, _diffs = store.upsert_listing(
            source_id=DAO_SOURCE,
            external_id=external_id,
            url=card["url"],
            title_raw=card["title"],
            title_norm=normalize_title(card["title"]),
            description=" · ".join(card["categories"]) or None,
            starts_at=_iso(card["start_date"], card["start_clock"]),
            ends_at=_iso(card["end_date"], card["end_clock"]),
            venue_id=venue_id,
            venue_name_raw=venue_name,
            image_url=card["image"] or None,
            raw_json=raw,
        )
        if action == "new":
            new += 1
        elif action == "changed":
            changed += 1
        else:
            unchanged += 1

    gone = store.mark_listings_missing(DAO_SOURCE, seen, "absent from downtown calendar")
    summary = Resolver(store).resolve()
    _relink_acts(store, city_id)
    summary.update({
        "cards": len(cards),
        "new": new,
        "changed": changed,
        "unchanged": unchanged,
        "gone": len(gone),
    })
    return summary


def _relink_acts(store: Store, city_id: str) -> None:
    """Replace title-scraped performer rows with the ones the title supports.

    Resolver calls split_performers on the raw title, which keeps series
    prefixes ("Main Street Sessions: …") as if they were the act. When we
    can read a cleaner billing, that replaces the guess. When we cannot,
    the resolver's rows stay.
    """
    rows = store.query(
        """
        SELECT e.id AS event_id, e.title, v.name AS venue_name
        FROM events e
        LEFT JOIN venues v ON v.id = e.venue_id
        WHERE e.active = 1
        """
    )
    for row in rows:
        acts = acts_from_title(row["title"] or "", row["venue_name"] or "")
        if not acts:
            continue
        store.execute(
            "DELETE FROM event_performers WHERE event_id = ?", (row["event_id"],)
        )
        venue_entity = None
        if row["venue_name"]:
            venue_entity = ensure_entity(
                store, name=row["venue_name"], kind="venue",
                parent_id=city_id, role="host",
            )
        for name, billing in acts:
            performer_id = store.ensure_performer(name, kind="band")
            store.link_performer(row["event_id"], performer_id, billing, name)
            band_id = ensure_entity(store, name=name, kind="band", role="act")
            if venue_entity:
                link(store, band_id, venue_entity, "plays_at", source_id=DAO_SOURCE)


def fill(db_path: Path = DB_PATH, page: str | None = None) -> dict:
    started = time.time()
    store = Store(db_path)
    try:
        store.upsert_source(OSM_SOURCE, "api", "https://www.openstreetmap.org/", interval_min=1440)
        store.upsert_source(DAO_SOURCE, "html", CALENDAR_URL, interval_min=180, min_delay_sec=5)
        city_id = ensure_entity(
            store, name="Metropolis", kind="city",
            meta={"note": "trunk", "downtown_bbox": list(DOWNTOWN_BBOX)},
        )
        rooms, failures = 0, []
        room_error = None
        # Shows first. A slow gazetteer must not block the calendar.
        if page is None:
            page = fetch_calendar()
        show_summary = ingest_shows(store, city_id, page)
        print(f"shows: {show_summary['cards']} cards, {show_summary['events']} events", flush=True)
        try:
            print("asking OpenStreetMap for downtown rooms...", flush=True)
            rooms, failures = ingest_rooms(store, city_id)
            print(f"rooms: {rooms}", flush=True)
            store.record_scan_result(OSM_SOURCE, "ok" if not failures else "error",
                                     seen=rooms, detail="; ".join(failures) or None)
        except discover.OverpassError as exc:
            room_error = str(exc)
            store.record_scan_result(OSM_SOURCE, "error", error_kind="http_error", detail=room_error)

        contact_summary = {"sites": 0, "written": 0, "errors": []}
        social_summary: dict = {"note": "", "listings": 0, "resolved": False}
        try:
            contact_summary = enrich_sites(store)
            print(f"sites: {contact_summary['sites']}, contact facts {contact_summary['written']}", flush=True)
            social_summary = probe_social(store, city_id)
            if social_summary.get("resolved"):
                _relink_acts(store, city_id)
            print(social_summary.get("note") or "social: nothing to check", flush=True)
        except Exception as exc:  # noqa: BLE001 - shows and rooms are already stored
            social_summary = {
                "note": f"Contact pages were not checked. {exc.__class__.__name__}.",
                "listings": 0,
                "resolved": False,
                "error": exc.__class__.__name__,
            }
            print(social_summary["note"], flush=True)

        store.record_scan_result(
            DAO_SOURCE, "ok",
            seen=show_summary["cards"],
            new=show_summary["new"],
            changed=show_summary["changed"],
            gone=show_summary["gone"],
            duration_ms=int((time.time() - started) * 1000),
        )
        return {
            "db": str(db_path),
            "rooms": rooms,
            "room_failures": failures,
            "room_error": room_error,
            "shows": show_summary,
            "contact": contact_summary,
            "social": social_summary,
            "filled_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        }
    finally:
        store.close()


def main() -> int:
    summary = fill()
    print(json.dumps(summary, indent=2))
    return 0 if summary["shows"]["cards"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
