"""Scraper hardening — social page login-wall workaround.

When a Facebook/Instagram/X page returns a login wall, try
alternative public URLs before giving up:
  1. Original URL (already tried)
  2. www subdomain variant
  3. Public page / posts variant
  4. Graph API public endpoint (Facebook only)

A walled page with no fallback yields no events — but the workaround
gives each page multiple chances, closing gaps the original scraper
left open.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from typing import Callable

from nightcal.social import (
    FACEBOOK, INSTAGRAM, X, SOCIAL_SOURCE,
    _NETWORKS, _PROFILE, _LABELS, _LOGIN_URL, _LOGIN_HTML,
    _SHARE_BITS, _EVENT_BITS, _JUNK_NAMES, _TYPE_KIND,
    network_of, social_url, social_rank,
    read_public_page, listings_from_page, ingest_listings,
    describe_probe,
    _fetch_public,
    _targets,
)
from towncrier.store import Store
from towncrier.entities import KIND_SOCIAL, add_item, ensure_entity
from towncrier.resolve import Resolver

# Facebook public page patterns that don't require login
_FB_PUBLIC_PATTERNS = [
    # /pages/name/id  — public pages often reachable without login
    r"https?://(?:www\.)?facebook\.com/pages/[^/]+/(\d+)",
    # /profile.php?id= — public profile by ID
    r"https?://(?:www\.)?facebook\.com/profile\.php\?id=(\d+)",
]

# Instagram public profile — the /<username>/ path is the public profile
_IG_PUBLIC_RE = re.compile(r"https?://(?:www\.)?instagram\.com/([^/?]+)")

# X public profile — /<username> is the public profile
_X_PUBLIC_RE = re.compile(r"https?://(?:www\.)?(?:x\.com|twitter\.com)/([^/?]+)")


def _fb_public_urls(original: str) -> list[str]:
    """Generate alternative public URLs for a Facebook page."""
    urls = []
    # Try without www
    urls.append(original.replace("://www.facebook.com", "://facebook.com"))
    # Try /posts/ variant — public posts page
    parsed = urllib.parse.urlparse(original)
    path = parsed.path.rstrip("/")
    if path and not path.endswith("/posts"):
        urls.append(f"https://www.facebook.com{path}/posts")
    # Try graph API public endpoint
    for pattern in _FB_PUBLIC_PATTERNS:
        m = re.match(pattern, original, re.I)
        if m:
            page_id = m.group(1)
            urls.append(f"https://graph.facebook.com/v18.0/{page_id}?fields=name,picture")
    return urls


def _ig_public_urls(original: str) -> list[str]:
    """Generate alternative public URLs for an Instagram page."""
    urls = []
    # Try without www
    urls.append(original.replace("://www.instagram.com", "://instagram.com"))
    # Try /p/ variant for specific posts
    m = _IG_PUBLIC_RE.match(original)
    if m:
        username = m.group(1)
        urls.append(f"https://www.instagram.com/{username}/")
    return urls


def _x_public_urls(original: str) -> list[str]:
    """Generate alternative public URLs for an X/Twitter page."""
    urls = []
    # Try without www
    urls.append(original.replace("://www.x.com", "://x.com"))
    urls.append(original.replace("://www.twitter.com", "://twitter.com"))
    # Try /i/user/ variant
    m = _X_PUBLIC_RE.match(original)
    if m:
        username = m.group(1)
        urls.append(f"https://x.com/i/user/{username}")
    return urls


_FALLBACK_MAP = {
    FACEBOOK: _fb_public_urls,
    INSTAGRAM: _ig_public_urls,
    X: _x_public_urls,
}


def _fetch_with_fallback(
    url: str,
    network: str,
    *,
    fetch: Callable[[str], dict] | None = None,
    timeout: int = 12,
) -> list[dict]:
    """Fetch a social page and its fallback URLs.

    Returns a list of fetch results (each with status/url/html/error),
    starting with the original URL, then fallbacks.
    Stops at the first successful (non-login, non-error) response.
    """
    if fetch is None:
        fetch = _fetch_public

    all_urls = [url] + _FALLBACK_MAP.get(network, lambda u: [])(url)
    results = []

    for attempt_url in all_urls:
        result = fetch(attempt_url)
        result["_attempt_url"] = attempt_url
        results.append(result)

        status = result.get("status", 0)
        html = result.get("html") or ""

        # Check if this response is a login wall
        is_login = _looks_like_login_html(html) or status in (401, 403)

        if not is_login and status not in (0, 404, 429) and status < 500:
            # Success — got real content past the wall (or no wall at all)
            break
        if is_login and status < 500:
            # Login wall — try next fallback
            continue
        # Error/timeout/server error — try next variant
        continue

    return results


def _looks_like_login_html(html: str) -> bool:
    """Check if HTML is a login wall."""
    if _LOGIN_URL.search(html):
        return True
    return any(marker in html for marker in _LOGIN_HTML)


def probe_social_hardened(
    store: Store,
    city_id: str,
    *,
    fetch: Callable[[str], dict] | None = None,
    today: date | None = None,
    timeout: int = 12,
) -> dict:
    """Hardened social probe with login-wall fallback chain.

    For each venue's social page, if the primary URL hits a login wall,
    tries alternative public URLs before giving up.
    """
    del city_id  # listings attach to the venue that cited the page
    fetch = fetch or _fetch_public
    today = today or date.today()
    counts = {
        key: {"probed": 0, "login": 0, "empty": 0, "error": 0, "events": 0}
        for key in (FACEBOOK, INSTAGRAM, X)
    }
    readable: dict[str, bool] = {FACEBOOK: True, INSTAGRAM: True, X: True}
    touched: set[str] = set()
    listings = []
    fallbacks_used: list[dict] = []

    for target in _targets(store):
        network = target["network"]
        if network not in counts:
            continue
        touched.add(network)

        # Try primary URL + fallbacks
        all_results = _fetch_with_fallback(target["url"], network, fetch=fetch)
        primary = all_results[0]

        counts[network]["probed"] += 1
        page = read_public_page(
            primary.get("html") or "",
            primary.get("url") or target["url"],
            int(primary.get("status") or 0),
        )

        # If primary hit a wall, try fallbacks
        if page["kind"] in ("login", "error"):
            fallback_used = False
            for fallback_result in all_results[1:]:
                fallback_page = read_public_page(
                    fallback_result.get("html") or "",
                    fallback_result.get("url") or "",
                    int(fallback_result.get("status") or 0),
                )
                if fallback_page["kind"] == "events":
                    page = fallback_page
                    fallback_used = True
                    fallbacks_used.append({
                        "network": network,
                        "primary_url": target["url"],
                        "fallback_url": fallback_result.get("url"),
                        "events": len(fallback_page.get("events", [])),
                    })
                    break
                elif fallback_page["kind"] == "empty":
                    continue
                elif fallback_page["kind"] in ("login", "error"):
                    # Another wall on this fallback — try the next one
                    continue
                else:
                    break  # unexpected kind, stop

            if fallback_used:
                counts[network]["probed"] += 1  # count the fallback attempt
            elif page["kind"] == "login":
                counts[network]["login"] += 1
            elif page["kind"] == "error":
                counts[network]["error"] += 1
        else:
            if page["kind"] == "empty":
                counts[network]["empty"] += 1

        if page["kind"] in ("login", "error"):
            readable[network] = False
            continue

        bound = listings_from_page(
            page["events"],
            network=network,
            page_url=primary.get("url") or target["url"],
            venue_id=target["venue_id"],
            venue_name=target["venue_name"],
            today=today,
        )
        counts[network]["events"] += len(bound)
        listings.extend(bound)

    complete = {network for network in touched if readable.get(network)}
    written = ingest_listings(store, listings, complete_sources=complete)
    note = describe_probe(counts)
    if fallbacks_used:
        note += f" Fallback URLs used: {len(fallbacks_used)}."
    store.upsert_source(SOCIAL_SOURCE, "html", None, interval_min=360)
    store.record_scan_result(SOCIAL_SOURCE, "ok", seen=sum(item["events"] for item in counts.values()), detail=note)
    return {
        "counts": counts,
        "note": note,
        "listings": len(listings),
        "fallbacks_used": fallbacks_used,
        **written,
    }