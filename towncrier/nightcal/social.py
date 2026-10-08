"""Public contact pages and public social listings.

A venue's own site is fetched the same way towncrier already enriches a
room: one GET, facts that the page actually states. Facebook, Instagram,
and X are the same kind of GET. A login wall is not a listing. A page
counts only when it contains a schema.org Event with a name and a
startDate. Nothing on this path sends a message to a room or a band.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

from nightcal.closures import is_closed
from towncrier.discover import USER_AGENT
from towncrier.normalize import normalize_title, parse_start
from towncrier.resolve import Resolver
from towncrier.store import Store

FACEBOOK = "facebook"
INSTAGRAM = "instagram"
X = "x"
SOCIAL_SOURCE = "social"

_NETWORKS = (
    ("facebook.com", FACEBOOK),
    ("fb.com", FACEBOOK),
    ("instagram.com", INSTAGRAM),
    ("twitter.com", X),
    ("x.com", X),
)
_PROFILE = {
    FACEBOOK: "https://www.facebook.com/",
    INSTAGRAM: "https://www.instagram.com/",
    "twitter": "https://x.com/",
    X: "https://x.com/",
}
_LABELS = {FACEBOOK: "Facebook", INSTAGRAM: "Instagram", X: "X"}
_TYPE_KIND = {
    "musicevent": "music",
    "comedyevent": "comedy",
    "theaterevent": "show",
    "theatrevent": "show",
    "screeningevent": "show",
    "danceevent": "show",
    "socialevent": "show",
    "visualartsevent": "show",
    "event": "show",
    "foodevent": "other",
    "businessevent": "other",
    "educationevent": "other",
    "sportsevent": "other",
}
_JUNK_NAMES = {
    "log in", "login", "sign in", "sign up", "facebook", "instagram", "twitter", "x", "home",
}
_LOGIN_URL = re.compile(
    r"(facebook\.com|fb\.com)/(login|checkpoint)|"
    r"instagram\.com/accounts/login|"
    r"(x\.com|twitter\.com)/(i/flow/login|login)",
    re.I,
)
_LOGIN_HTML = (
    "You must log in to continue",
    "Log in to Facebook",
    "Log Into Facebook",
    "Log into Facebook",
    'id="login_form"',
    "login_form",
    "Log in to Instagram",
    "Login • Instagram",
    "Log in • Instagram",
    "/accounts/login/",
    "Sign in to X",
)
_SHARE_BITS = ("/sharer", "/share.php", "/share?", "/intent/", "/dialog/")
_EVENT_BITS = ("/events/", "/p/", "/reel/", "/status/", "/posts/")


def network_of(url: str) -> str | None:
    host = _host(url)
    for domain, network in _NETWORKS:
        if host == domain or host.endswith("." + domain):
            return network
    return None


def _host(value: str) -> str:
    text = (value or "").strip()
    if "://" not in text:
        text = "//" + text
    host = text.split("//", 1)[1].split("/", 1)[0].lower()
    if "@" in host:
        host = host.split("@", 1)[1]
    if host.startswith("www."):
        host = host[4:]
    return host.split(":", 1)[0]


def social_url(network: str, raw: str) -> str | None:
    """A profile URL from a tag the source already stated.

    A bare handle becomes that network's profile. An http URL on the same
    host is stored as https so the calendar can link it. A share button or
    a login URL is not a profile.
    """
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("http://") or text.startswith("https://"):
        return _clean_social(text)
    if "/" in text or text.startswith("www."):
        return _clean_social("https://" + text.lstrip("/"))
    handle = text.lstrip("@").strip().strip("/")
    if not handle or any(ch in handle for ch in " /?&#"):
        return None
    base = _PROFILE.get(network)
    if not base:
        return None
    return base + handle


def _clean_social(url: str) -> str | None:
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    if not url.startswith("https://"):
        return None
    if network_of(url) is None:
        return None
    parts = urllib.parse.urlsplit(url)
    path = parts.path or "/"
    lowered = path.lower()
    if any(bit in (lowered + "?" + parts.query.lower()) for bit in _SHARE_BITS):
        return None
    if _LOGIN_URL.search(url):
        return None
    cleaned = urllib.parse.urlunsplit(("https", parts.netloc, path.rstrip("/") or "/", "", ""))
    return cleaned


def social_rank(url: str) -> tuple[int, int]:
    """Profiles sort ahead of posts and event pages. Shorter paths win ties."""
    path = urllib.parse.urlsplit(url).path.lower()
    eventish = 1 if any(bit in path for bit in _EVENT_BITS) else 0
    return (eventish, len(path))


def _walk(data):
    if isinstance(data, list):
        for item in data:
            yield from _walk(item)
    elif isinstance(data, dict):
        yield data
        for value in data.values():
            if isinstance(value, (dict, list)):
                yield from _walk(value)


def _ld_text(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("@value", "name", "text"):
            found = value.get(key)
            if isinstance(found, str) and found.strip():
                return found.strip()
    if isinstance(value, list):
        for item in value:
            found = _ld_text(item)
            if found:
                return found
    return ""


def _event_kind(types: list[str]) -> str | None:
    mapped = []
    for raw in types:
        key = raw.split("/")[-1].split(":")[-1].lower()
        if key in _TYPE_KIND:
            mapped.append(_TYPE_KIND[key])
    if not mapped:
        return None
    for prefer in ("music", "comedy", "show", "other"):
        if prefer in mapped:
            return prefer
    return None


def _jsonld_events(html: str) -> list[dict]:
    found = []
    seen: set[tuple[str, str]] = set()
    for raw in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html or "",
        re.I | re.S,
    ):
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in _walk(data):
            types = node.get("@type") or node.get("type") or []
            if isinstance(types, str):
                types = [types]
            types = [item for item in types if isinstance(item, str)]
            kind = _event_kind(types)
            if not kind:
                continue
            name = _ld_text(node.get("name"))
            start = _ld_text(node.get("startDate"))
            if not name or not start or name.casefold() in _JUNK_NAMES:
                continue
            if len(name) > 180:
                continue
            key = (name.casefold(), start)
            if key in seen:
                continue
            seen.add(key)
            found.append({
                "name": name,
                "start": start,
                "end": _ld_text(node.get("endDate")),
                "url": _ld_text(node.get("url")),
                "kind": kind,
                "description": _ld_text(node.get("description"))[:400],
            })
    return found


def _looks_like_login(final_url: str, html: str) -> bool:
    if _LOGIN_URL.search(final_url or ""):
        return True
    text = html or ""
    return any(marker in text for marker in _LOGIN_HTML)


def read_public_page(html: str, final_url: str, status: int) -> dict:
    """Classify one fetched page. A wall yields no events, even if the HTML has one."""
    if status in (0, 404, 429) or status >= 500:
        return {"kind": "error", "events": []}
    if status in (401, 403) or _LOGIN_URL.search(final_url or ""):
        return {"kind": "login", "events": []}
    events = _jsonld_events(html)
    if events:
        return {"kind": "events", "events": events}
    if _looks_like_login(final_url, html):
        return {"kind": "login", "events": []}
    return {"kind": "empty", "events": []}


def _cite_url(event_url: str, page_url: str, network: str) -> str | None:
    cleaned = _clean_social(event_url) if event_url else None
    if cleaned and network_of(cleaned) == network:
        return cleaned
    page = _clean_social(page_url)
    if page and network_of(page) == network:
        return page
    return None


def listings_from_page(
    events: list[dict],
    *,
    network: str,
    page_url: str,
    venue_id: str | None,
    venue_name: str,
    today: date,
) -> list[dict]:
    """Turn already-classified events into listing rows. Dates outside the window are dropped."""
    rows = []
    window_start = today - timedelta(days=14)
    window_end = today + timedelta(days=180)
    for event in events:
        cited = _cite_url(event.get("url") or "", page_url, network)
        if not cited:
            continue
        parsed = parse_start(iso=event.get("start") or "", tz_name="America/Los_Angeles", today=today)
        if not parsed:
            continue
        starts_at, local_date, _tz, _hour, _minute = parsed
        try:
            day = date.fromisoformat(local_date)
        except ValueError:
            continue
        if day < window_start or day > window_end:
            continue
        end = None
        if event.get("end"):
            end_parsed = parse_start(iso=event["end"], tz_name="America/Los_Angeles", today=today)
            if end_parsed:
                end = end_parsed[0]
        start_raw = event.get("start") or ""
        all_day = "T" not in start_raw and len(start_raw) <= 10
        rows.append({
            "network": network,
            "external_id": f"{network}|{normalize_title(event['name'])}|{local_date}|{cited}",
            "url": cited,
            "title": event["name"],
            "starts_at": starts_at,
            "ends_at": end,
            "all_day": all_day,
            "venue_id": venue_id,
            "venue_name": venue_name,
            "kind": event.get("kind") or "show",
            "description": event.get("description") or "",
            "local_date": local_date,
            "page": page_url,
        })
    return rows


def ingest_listings(store: Store, listings: list[dict], *, complete_sources: set[str]) -> dict:
    """Write social listings. Other sources are not marked missing.

    A source is complete only when every page we asked it for was actually
    readable. A login wall or a timeout leaves that source's older listings
    in place.
    """
    counts = {"new": 0, "changed": 0, "unchanged": 0, "gone": 0, "events": 0}
    by_source: dict[str, set[str]] = {source: set() for source in complete_sources}
    for row in listings:
        source_id = row["network"]
        store.upsert_source(source_id, "html", f"https://{_LABELS[source_id].lower()}.com/", interval_min=360)
        _listing_id, action, _diffs = store.upsert_listing(
            source_id=source_id,
            external_id=row["external_id"],
            url=row["url"],
            title_raw=row["title"],
            title_norm=normalize_title(row["title"]),
            description=row["description"] or None,
            starts_at=row["starts_at"],
            ends_at=row["ends_at"],
            all_day=row["all_day"],
            venue_id=row["venue_id"],
            venue_name_raw=row["venue_name"],
            raw_json={
                "kind": row["kind"],
                "categories": [_LABELS[source_id]],
                "local_date": row["local_date"],
                "network": source_id,
                "page": row["page"],
            },
        )
        counts[action] += 1
        if source_id in by_source:
            by_source[source_id].add(row["external_id"])
    for source_id, seen in by_source.items():
        store.upsert_source(source_id, "html", None, interval_min=360)
        gone = store.mark_listings_missing(source_id, seen, "absent from the public page")
        counts["gone"] += len(gone)
    wrote = counts["new"] or counts["changed"] or counts["gone"]
    if wrote:
        summary = Resolver(store).resolve()
        counts["events"] = summary.get("events") or 0
        counts["resolved"] = True
    else:
        counts["resolved"] = False
    return counts


def _fetch_public(url: str, timeout: int = 12) -> dict:
    """One GET. No cookies and no login. The final URL is what we classify."""
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(1_500_000)
            charset = response.headers.get_content_charset() or "utf-8"
            return {
                "status": response.status,
                "url": response.geturl(),
                "html": raw.decode(charset, "replace"),
                "error": "",
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(200_000) if exc.fp else b""
        return {
            "status": exc.code,
            "url": exc.geturl() or url,
            "html": body.decode("utf-8", "replace"),
            "error": "",
        }
    except Exception as exc:  # noqa: BLE001 - a dead page is a result, not a crash
        return {"status": 0, "url": url, "html": "", "error": exc.__class__.__name__}


def _targets(store: Store) -> list[dict]:
    rows = store.query(
        """
        SELECT i.value AS url, e.name AS name, v.id AS venue_id
        FROM items i
        JOIN entities e ON e.id = i.entity_id
        LEFT JOIN venues v ON v.name = e.name
        WHERE i.kind = 'social' AND e.kind = 'venue'
        """
    )
    found = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if is_closed(row["name"] or ""):
            continue
        url = _clean_social(row["url"] or "")
        if not url:
            continue
        key = (url, row["venue_id"] or row["name"])
        if key in seen:
            continue
        seen.add(key)
        found.append({
            "url": url,
            "network": network_of(url),
            "venue_id": row["venue_id"],
            "venue_name": row["name"],
        })
    found.sort(key=lambda item: (social_rank(item["url"]), item["venue_name"], item["url"]))
    return found[:24]


def describe_probe(counts: dict[str, dict]) -> str:
    """One plain sentence. A wall is named. Zero events stay zero."""
    labels = _LABELS
    probed = sum(item["probed"] for item in counts.values())
    if not probed:
        return "No room cited a public Facebook, Instagram, or X page."
    parts = []
    taken = 0
    for key in (FACEBOOK, INSTAGRAM, X):
        item = counts.get(key) or {"probed": 0, "login": 0, "empty": 0, "error": 0, "events": 0}
        if not item["probed"]:
            continue
        name = labels[key]
        taken += item["events"]
        if item["events"]:
            noun = "show" if item["events"] == 1 else "shows"
            parts.append(f"{name} listed {item['events']} {noun}")
        elif item["login"] == item["probed"]:
            parts.append(f"{name} asked for a login")
        elif item["error"] == item["probed"]:
            parts.append(f"{name} did not answer")
        else:
            bits = []
            if item["login"]:
                bits.append(f"{item['login']} asked for a login")
            if item["empty"]:
                bits.append(f"{item['empty']} listed no show")
            if item["error"]:
                bits.append(f"{item['error']} did not answer")
            parts.append(f"{name}: " + ", ".join(bits))
    sentence = ". ".join(parts) + "."
    if taken == 0:
        sentence += " Nothing was added from a page that did not list a show."
    return sentence


def probe_social(
    store: Store,
    city_id: str,
    *,
    fetch=None,
    today: date | None = None,
    timeout: int = 12,
) -> dict:
    """GET each cited social page and keep only events that page actually lists."""
    del city_id  # listings attach to the venue that cited the page
    fetch = fetch or (lambda url: _fetch_public(url, timeout))
    today = today or date.today()
    counts = {
        key: {"probed": 0, "login": 0, "empty": 0, "error": 0, "events": 0}
        for key in (FACEBOOK, INSTAGRAM, X)
    }
    readable: dict[str, bool] = {FACEBOOK: True, INSTAGRAM: True, X: True}
    touched: set[str] = set()
    listings = []
    for target in _targets(store):
        network = target["network"]
        if network not in counts:
            continue
        touched.add(network)
        fetched = fetch(target["url"])
        page = read_public_page(fetched.get("html") or "", fetched.get("url") or target["url"], int(fetched.get("status") or 0))
        counts[network]["probed"] += 1
        if page["kind"] in ("login", "empty", "error"):
            counts[network][page["kind"]] += 1
        if page["kind"] in ("login", "error"):
            readable[network] = False
            continue
        bound = listings_from_page(
            page["events"],
            network=network,
            page_url=fetched.get("url") or target["url"],
            venue_id=target["venue_id"],
            venue_name=target["venue_name"],
            today=today,
        )
        counts[network]["events"] += len(bound)
        listings.extend(bound)
    complete = {network for network in touched if readable.get(network)}
    written = ingest_listings(store, listings, complete_sources=complete)
    note = describe_probe(counts)
    store.upsert_source(SOCIAL_SOURCE, "html", None, interval_min=360)
    store.record_scan_result(SOCIAL_SOURCE, "ok", seen=sum(item["events"] for item in counts.values()), detail=note)
    return {"counts": counts, "note": note, "listings": len(listings), **written}


def _site_url(value: str) -> str | None:
    text = (value or "").strip()
    if not text or text.lower().startswith("osm:"):
        return None
    if text.startswith("http://"):
        text = "https://" + text[len("http://"):]
    if not text.startswith("https://"):
        if " " in text or "@" in text:
            return None
        text = "https://" + text.lstrip("/")
    if network_of(text):
        return None
    return text


def enrich_sites(store: Store, *, timeout: int = 12) -> dict:
    """Fetch each open room's own site and write the contact facts it states."""
    from towncrier import facts

    rows = store.query(
        """
        SELECT i.entity_id, i.value AS url, e.name AS name
        FROM items i
        JOIN entities e ON e.id = i.entity_id
        WHERE i.kind = 'website' AND e.kind = 'venue'
        """
    )
    seen: set[str] = set()
    written = 0
    errors: list[str] = []
    checked = 0
    for row in rows:
        if checked >= 12:
            break
        if is_closed(row["name"] or ""):
            continue
        url = _site_url(row["url"] or "")
        if not url or url in seen:
            continue
        seen.add(url)
        checked += 1
        try:
            result = facts.enrich_venue(store, row["entity_id"], url, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 - one dead site does not stop the others
            errors.append(f"{row['name']}: {exc.__class__.__name__}")
            continue
        written += int(result.get("written") or 0)
        if result.get("error"):
            errors.append(f"{row['name']}: {result['error']}")
    return {"sites": checked, "written": written, "errors": errors}


def social_status(store: Store) -> str:
    """The last probe sentence, if this store has been checked."""
    row = store.one(
        """
        SELECT detail FROM scans
        WHERE source_id = ? AND detail IS NOT NULL AND detail != ''
        ORDER BY id DESC LIMIT 1
        """,
        (SOCIAL_SOURCE,),
    )
    if row is None:
        return ""
    return row["detail"] or ""
