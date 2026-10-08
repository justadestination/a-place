"""Tests for social_hardened fallback chain."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import date
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shadenet.nightcal.social_hardened import (
    _fb_public_urls,
    _ig_public_urls,
    _x_public_urls,
    _fetch_with_fallback,
    _looks_like_login_html,
)

PASS = 0
FAIL = 0


def check(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}\n       got:  {got!r}\n       want: {want!r}")


def ok(label, cond):
    check(label, bool(cond), True)


def test_fb_fallback_urls():
    url = "https://www.facebook.com/russianriverbrewing"
    fallbacks = _fb_public_urls(url)
    ok("has at least one fallback", len(fallbacks) >= 1)
    check("non-www variant present", any("facebook.com/russianriverbrewing" in u and "www." not in u for u in fallbacks), True)
    check("posts variant exists", any("/posts" in u for u in fallbacks), True)


def test_ig_fallback_urls():
    url = "https://www.instagram.com/russianriverbrewingofficial"
    fallbacks = _ig_public_urls(url)
    ok("has fallback", len(fallbacks) >= 1)


def test_x_fallback_urls():
    url = "https://x.com/syrahchef"
    fallbacks = _x_public_urls(url)
    ok("has fallback", len(fallbacks) >= 1)


def test_login_wall_detection():
    ok("facebook login", _looks_like_login_html("Log in to Facebook"))
    ok("instagram login", _looks_like_login_html("Log in to Instagram"))
    ok("x login", _looks_like_login_html("Sign in to X"))
    ok("clean page", not _looks_like_login_html("<html><body>Show tonight</body></html>"))


def test_fetch_with_fallback():
    call_log = []
    call_count = [0]

    def mock_fetch(url):
        call_log.append(url)
        call_count[0] += 1
        # URL 1 = the walled primary (contains "wall")
        if call_count[0] == 1:
            return {"status": 200, "url": url, "html": "Log in to Facebook", "error": ""}
        # All subsequent URLs = real content with events
        return {"status": 200, "url": url, "html": '<script type="application/ld+json">{"@type":"MusicEvent","name":"Show","startDate":"2026-10-15T21:00:00-07:00"}</script>', "error": ""}

    results = _fetch_with_fallback("https://www.facebook.com/wall", "facebook", fetch=mock_fetch)
    ok("tried primary + fallback", len(results) >= 2)
    # The fallback URLs (not the primary "wall" URL) get real content
    ok("fallback succeeded", len(results) > 1)


def test_fetch_with_fallback_no_wall():
    call_log = []
    def mock_fetch(url):
        call_log.append(url)
        return {"status": 200, "url": url, "html": '<script type="application/ld+json">{"@type":"MusicEvent","name":"Show","startDate":"2026-10-15T21:00:00-07:00"}</script>', "error": ""}

    results = _fetch_with_fallback("https://www.facebook.com/good", "facebook", fetch=mock_fetch)
    check("only primary tried (no wall)", len(results), 1)


def test_probe_social_hardened():
    from shadenet.nightcal.social_hardened import probe_social_hardened
    from towncrier.store import Store
    from towncrier.entities import ensure_entity, KIND_SOCIAL, add_item

    tmp = Path(tempfile.mkdtemp(prefix="nightcal-hardened-"))
    store = Store(tmp / "t.db")
    city = ensure_entity(store, name="Metropolis", kind="city")
    vid = ensure_entity(store, name="Test Venue", kind="venue", parent_id=city, role="host")
    store.ensure_venue("Test Venue", city="Metropolis", state="CA")

    add_item(store, entity_id=vid, kind=KIND_SOCIAL,
             value="https://www.facebook.com/testvenue", display="Facebook",
             source_id="test", source_url="https://example.com", citation_kind="html")

    def mock_fetch(url):
        if "facebook.com" in url and "/posts" not in url:
            return {"status": 200, "url": url, "html": "Log in to Facebook", "error": ""}
        if "facebook.com" in url and "/posts" in url:
            return {"status": 200, "url": url, "html": '<script type="application/ld+json">{"@context":"https://***@graph","@graph":[{"@type":"MusicEvent","name":"Fallback Show","startDate":"2026-10-20T21:00:00-07:00"}]}</script>', "error": ""}
        return {"status": 0, "url": url, "html": "", "error": "URLError"}

    result = probe_social_hardened(store, "city", fetch=mock_fetch, today=date(2026, 10, 7))
    check("fb probed with fallback", result["counts"]["facebook"]["probed"], 2)
    check("fb events from fallback", result["counts"]["facebook"]["events"], 1)
    check("fallbacks recorded", len(result.get("fallbacks_used", [])), 1)
    ok("note mentions fallbacks", "Fallback URLs used" in result["note"])
    store.close()


def main():
    tests = [
        test_fb_fallback_urls,
        test_ig_fallback_urls,
        test_x_fallback_urls,
        test_login_wall_detection,
        test_fetch_with_fallback,
        test_fetch_with_fallback_no_wall,
        test_probe_social_hardened,
    ]
    for t in tests:
        t()
    print("=" * 70)
    print(f"{PASS} passed, {FAIL} failed")
    print("=" * 70)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())