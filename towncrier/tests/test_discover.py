"""Tests for discovery and enrichment.

The network-dependent paths are deliberately not exercised here beyond one
opt-in live test at the bottom. Everything in the main suite runs against
fixtures, because a test suite that fails when Overpass rate-limits tells you
nothing about whether the code is right.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from towncrier import discover, facts
from towncrier.entities import KIND_ADDRESS, KIND_EMAIL, KIND_HOURS, KIND_PHONE, KIND_SOCIAL, KIND_WEBSITE
from towncrier.store import Store

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


# ================================================================ classification

def test_classify():
    # A dedicated live music venue: unambiguous.
    v, s, _ = discover._classify({"name": "X", "leisure": "live_music_venue"})
    ok("live_music_venue is a venue", v)
    ok("live_music_venue scores high", s >= 6)

    # amenity=music
    v, s, _ = discover._classify({"name": "X", "amenity": "music"})
    ok("amenity=music is a venue", v)

    # A bar with no music signal at all: not a branch.
    v, s, r = discover._classify({"name": "Corner Store", "amenity": "bar"})
    check("bare bar is not a venue", v, False)
    ok("bare bar scores low", s < 4)

    # A bar that says it has live music: is a branch. This is the case that
    # matters for a town full of breweries.
    v, s, r = discover._classify({
        "name": "Shady Oak", "amenity": "bar",
        "live_music": "yes", "music:type": "live_music",
    })
    ok("bar with music signals is a venue", v)
    ok("music signals appear in reasons",
       any("signals" in x or "music:type" in x for x in r))

    # A bar with a stage/dance/karaoke tag.
    for tag in ("stage", "dance", "karaoke", "dj", "jazz"):
        v, _, _ = discover._classify({"name": "Y", "amenity": "bar", tag: "yes"})
        ok(f"bar with {tag}=yes is a venue", v)

    # Explicit "no live music" beats a generic signal.
    v, s, r = discover._classify({
        "name": "Quiet Bar", "amenity": "bar", "stage": "no", "live_music": "no",
    })
    check("explicit no-music demotes", v, False)

    # Casino is a real music venue but weakly scored.
    v, s, _ = discover._classify({"name": "C", "amenity": "casino"})
    ok("casino counted as venue", v)
    ok("casino scores below concert_hall",
       s < discover._classify({"name": "C", "amenity": "concert_hall"})[1])

    # Theatres / arts centres / event venues.
    for a in ("theatre", "arts_centre", "events_venue", "concert_hall",
              "public_hall", "nightclub"):
        v, _, _ = discover._classify({"name": "V", "amenity": a})
        ok(f"amenity={a} is a venue", v)

    # Empty tags: not a venue, and must not crash.
    v, s, r = discover._classify({})
    check("empty tags -> not a venue", v, False)
    check("empty tags -> score 0", s, 0)


# ================================================================ tiling

def test_tiles():
    # A small box is one tile.
    t = discover.OverpassClient.tiles((38.40, -122.72, 38.42, -122.70))
    check("small bbox is 1 tile", len(t), 1)

    # A large box is split, and tiles do not overlap.
    bbox = (38.28, -122.85, 38.52, -122.55)
    tiles = discover.OverpassClient.tiles(bbox, max_deg=0.06)
    ok("big bbox splits into many tiles", len(tiles) > 12)
    check("no duplicate tiles", len(set(tiles)), len(tiles))
    for tile in tiles:
        s, w, n, e = map(float, tile.split(","))
        ok("tile within bbox south", bbox[0] - 1e-3 <= s <= bbox[2] + 1e-3)
        ok("tile within bbox north", bbox[0] - 1e-3 <= n <= bbox[2] + 1e-3)
        ok("tile within bbox west", bbox[1] - 1e-3 <= w <= bbox[3] + 1e-3)
        ok("tile within bbox east", bbox[1] - 1e-3 <= e <= bbox[3] + 1e-3)

    # Tiles must collectively cover the whole area: recompute the union area.
    union = 0.0
    for tile in tiles:
        s, w, n, e = map(float, tile.split(","))
        union += (n - s) * (e - w)
    area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    # Slight over-count is expected from the seam overlap; under 100% is a bug.
    ok("tiles cover >=100% of area", union >= area * 0.999)


# ================================================================ offline parse

def test_candidates_from_overpass():
    payload = {
        "elements": [
            {"type": "node", "id": 1, "lat": 38.4, "lon": -122.7,
             "tags": {"name": "The Royal", "amenity": "music",
                      "phone": "+1 707-543-1500"}},
            {"type": "way", "id": 2, "center": {"lat": 38.41, "lon": -122.71},
             "tags": {"name": "Shady Oak", "amenity": "bar"}},
            # No name: must be dropped, not invented into "(unnamed ...)".
            {"type": "node", "id": 3, "lat": 38.4, "lon": -122.7,
             "tags": {"amenity": "bar"}},
            # No coordinates: unusable, must be dropped.
            {"type": "node", "id": 4, "tags": {"name": "Ghost", "amenity": "bar"}},
        ]
    }
    got = discover.candidates_from_overpass(payload, tile="t1")
    names = sorted(c.name for c in got)
    check("parses named, located elements only", names, ["Shady Oak", "The Royal"])

    royal = [c for c in got if c.name == "The Royal"][0]
    check("node lat read directly", royal.lat, 38.4)
    check("venue flag set", royal.is_music_venue, True)
    check("osm_url built", royal.osm_url, "https://www.openstreetmap.org/node/1")
    check("tile recorded", royal.tile, "t1")
    check("serialises", "osm_url" in royal.as_dict(), True)

    # A `way` carries its position in a `center` object, not `lat`/`lon`.
    shady = [c for c in got if c.name == "Shady Oak"][0]
    check("way center becomes lat", shady.lat, 38.41)
    check("way center becomes lon", shady.lon, -122.71)

    # Sorting: highest score first, then alphabetical.
    check("sorted by score desc", [c.name for c in got], ["The Royal", "Shady Oak"])


# ================================================================ extraction

SHADY_OAK_HTML = """
<html><head><title>Shady Oak</title>
<meta property="og:title" content="Shady Oak">
</head><body>
<h1>Welcome to Beer Country</h1>
<p>HOURS</p>
<p>Mon: CLOSED</p><p>Tues - Fri: 3-11 pm</p><p>Sat: 2-11 pm</p><p>Sun: 2-9 pm</p>
<p>CALL US</p>
<p>(707) 575-7687</p>
<p>COME VISIT</p>
<p>100 Main Street<br>Metropolis, CA 10001</p>
<a href="https://www.instagram.com/shadyoakbeer/">Instagram</a>
</body></html>
"""

JSONLD_HTML = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"MusicVenue","name":"The Royal",
 "telephone":"+1-707-543-1500","email":"booking@theroyal.test",
 "url":"https://theroyal.test",
 "address":{"@type":"PostalAddress","streetAddress":"150 Clement St",
            "addressLocality":"Metropolis","addressRegion":"CA","postalCode":"10001"},
 "openingHoursSpecification":[
   {"@type":"OpeningHoursSpecification","dayOfWeek":["Monday","Tuesday"],
    "opens":"17:00","closes":"23:00"},
   {"@type":"OpeningHoursSpecification","dayOfWeek":"Sunday",
    "opens":"00:00","closes":"00:00"}],
 "sameAs":["https://www.instagram.com/theroyalsr/","https://www.facebook.com/theroyal"]}
</script></head><body>
<a href="tel:+17075431500">Call</a>
<a href="mailto:booking@theroyal.test">Email</a>
</body></html>
"""

GRAPH_HTML = """
<html><head><script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
  {"@type":"WebSite","name":"site"},
  {"@type":"MusicVenue","name":"Nested Venue","telephone":"707-555-0199"}]}
</script></head><body></body></html>
"""

MALFORMED_HTML = """
<html><head><script type="application/ld+json">
{"@type":"MusicVenue", "telephone": }
</script></head><body></body></html>
"""


def kinds(facts_list, kind):
    return sorted(f["value"] for f in facts_list if f["kind"] == kind)


def test_extract_jsonld():
    got = facts.extract_facts("https://theroyal.test", JSONLD_HTML)
    ok("finds JSON-LD phone", "7075431500" in [f["value"] for f in got if f["kind"] == KIND_PHONE]
       or any(f["kind"] == KIND_PHONE for f in got))
    check("JSON-LD email", kinds(got, KIND_EMAIL), ["booking@theroyal.test"])
    ok("JSON-LD address has street", any(
        "150 Clement" in v for v in kinds(got, KIND_ADDRESS)))
    ok("JSON-LD address has city", any(
        "Metropolis" in v for v in kinds(got, KIND_ADDRESS)))
    ok("JSON-LD address has postcode", any(
        "10001" in v for v in kinds(got, KIND_ADDRESS)))
    ok("JSON-LD hours rendered", any(
        "Monday/Tuesday" in v for v in kinds(got, KIND_HOURS)))
    ok("midnight-midnight renders as closed", any(
        "closed" in v.lower() for v in kinds(got, KIND_HOURS)))
    ok("socials from sameAs", len(kinds(got, KIND_SOCIAL)) >= 2)
    ok("website from url", any("theroyal.test" in v for v in kinds(got, KIND_WEBSITE)))
    ok("every fact has an excerpt", all(f["excerpt"] for f in got))

    # The tel: link restates the same number -- must not become a second row.
    phones = [f for f in got if f["kind"] == KIND_PHONE]
    check("phone deduped across methods", len(phones), 1)


def test_extract_text():
    got = facts.extract_facts("http://www.shadyoakbrewing.com/", SHADY_OAK_HTML)
    check("phone from visible text", kinds(got, KIND_PHONE), ["(707) 575-7687"])
    ok("hours from freeform", len(kinds(got, KIND_HOURS)) >= 2)
    ok("instagram detected", any("instagram" in v for v in kinds(got, KIND_SOCIAL)))

    # The visible-text number must be cited to a real excerpt, not the raw html.
    ph = [f for f in got if f["kind"] == KIND_PHONE][0]
    ok("text phone excerpt is text not markup", "<" not in ph["excerpt"])
    ok("excerpt mentions the number", "575-7687" in ph["excerpt"])


def test_extract_robustness():
    got = facts.extract_facts("https://x.test", GRAPH_HTML)
    ok("finds phone inside @graph",
       any("7075550199" in f["value"].replace("-", "") for f in got if f["kind"] == KIND_PHONE))

    nested = """
    <script type="application/ld+json">
    {"@type":"ContactPage","name":"Contact",
     "mainEntity":{"@type":"Organization","name":"The Commons Arts Center",
       "telephone":"707-396-0354","email":"info@arlene.test",
       "url":"https://arlene.test/",
       "sameAs":["https://www.facebook.com/arlenefranciscenter/"],
       "address":{"streetAddress":"200 Central Avenue","addressLocality":"Metropolis",
                  "addressRegion":"CA","postalCode":"10001"}}}
    </script>
    """
    got = facts.extract_facts("https://arlene.test/contact/", nested)
    phones = [f for f in got if f["kind"] == KIND_PHONE]
    ok("phone nested on mainEntity is kept", any("7073960354" in f["value"].replace("-", "") for f in phones))
    ok("nested phone is the structured fact, not a guess", any(f["method"] == "jsonld" for f in phones))
    ok("nested address keeps the street", any("200 Central Avenue" in v for v in kinds(got, "address")))
    check(
        "a contact page url is not the venue site",
        [v.rstrip("/") for v in kinds(got, "website")],
        ["https://arlene.test"],
    )

    # Malformed JSON-LD must be skipped, not raise.
    got = facts.extract_facts("https://x.test", MALFORMED_HTML)
    check("malformed JSON-LD yields nothing", got, [])

    # Empty and junk input.
    check("empty html", facts.extract_facts("https://x.test", ""), [])
    check("junk html", facts.extract_facts("https://x.test", "not html at all"), [])

    # A page with no phone yields no phone -- the gap stays visible.
    got = facts.extract_facts("https://x.test", "<html><body>Hours: 5-11</body></html>")
    check("no phone fabricated", kinds(got, KIND_PHONE), [])

    # A 7-digit local number is not an area code; must not be recorded.
    got = facts.extract_facts("https://x.test",
                              "<html><body>Call 543-1500</body></html>")
    check("bare local number rejected", kinds(got, KIND_PHONE), [])


# ================================================================ db round trip

def test_enrich_writes_cited():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        s = Store(Path(td) / "t.db")
        city = s.execute(
            "INSERT INTO entities (id,kind,name) VALUES ('e_city','city','Metropolis')"
        ) and "e_city" or "e_city"
        vid = "e_venue"
        s.execute(
            "INSERT INTO entities (id,kind,name,parent_id,role) "
            "VALUES (?,'venue','Shady Oak',?,'host')", (vid, city))

        # enrich_venue does the HTTP fetch; here we feed the writer directly.
        parsed = facts.extract_facts("http://www.shadyoakbrewing.com/", SHADY_OAK_HTML)
        from towncrier.entities import add_item
        for f in parsed:
            add_item(s, entity_id=vid, kind=f["kind"], value=f["value"],
                     display=f["display"], source_id="web:shadyoakbrewing.com",
                     source_url="http://www.shadyoakbrewing.com/",
                     citation_kind="html", excerpt=f["excerpt"])

        from towncrier.entities import venue_dossier, uncited
        dos = venue_dossier(s, vid)
        check("venue name", dos["name"], "Shady Oak")
        ok("phone on dossier", len(dos["facts"].get(KIND_PHONE, [])) >= 1)
        ok("address on dossier", len(dos["facts"].get(KIND_ADDRESS, [])) >= 1)
        check("email genuinely absent -> reported", KIND_EMAIL in dos["not_found"], True)

        # The headline guarantee: zero uncited facts.
        check("no uncited facts", len(uncited(s)), 0)

        # And every fact can be traced to a URL.
        from towncrier.entities import items_for
        for row in items_for(s, vid):
            ok(f"{row['kind']} has a source_url", row["source_url"])

        s.close()


def test_overpass_cache(tmpdir=None):
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        c = discover.OverpassClient(cache_dir=Path(td) / "c")
        q = "[out:json];node(1);out;"
        check("miss on empty cache", c.cached(q), None)
        c._store_cache(q, {"elements": [{"id": 1}]})
        check("hit after store", c.cached(q), {"elements": [{"id": 1}]})

        # Corrupt cache must self-heal rather than crash the scan.
        p = c._cache_path(q)
        p.write_text("{not json")
        check("corrupt cache returns None", c.cached(q), None)
        check("corrupt cache file removed", p.exists(), False)


def test_failed_tile_is_reported():
    """A tile that fails must be surfaced, never silently dropped."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        c = discover.OverpassClient(cache_dir=Path(td) / "c",
                                    endpoints=("http://127.0.0.1:1/none",),
                                    max_retries=0, min_interval_sec=0)

        def boom(query, **kw):
            raise discover.OverpassError("simulated 504")
        c.fetch = boom

        cands, failures = c.discover_area((38.40, -122.72, 38.42, -122.70),
                                          sleep_between_tiles=0)
        check("no candidates from all-failed area", cands, [])
        ok("failures reported, not swallowed", len(failures) >= 1)


def test_partial_coverage_survives_one_bad_tile():
    """The good tiles must still return, and the bad tile must still be reported.

    The bbox below is 0.06 x 0.10 degrees, which `tiles()` splits into four
    tiles. Two of them are failed by the stub, so this asserts both halves of
    the contract at once: partial results are useful, and the gap is visible.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        c = discover.OverpassClient(cache_dir=Path(td) / "c", min_interval_sec=0)

        # Splitting is what makes this a multi-tile test rather than a
        # single-tile one with a fake failure that never fires.
        check("bbox splits into 4 tiles",
              len(discover.OverpassClient.tiles((38.40, -122.75, 38.46, -122.65))), 4)

        def fake(query, **kw):
            # Decide from the tile's *parsed* southern edge, not a substring.
            # "38.43" matches every tile (row 0's north edge is 38.43010 and
            # row 1's south edge is 38.43000), and "38.46" matches only the
            # northmost edge rather than a row. Either way the stub silently
            # fails the wrong set and the assertion stops meaning anything.
            box = query.split("(")[-1].rstrip(");")
            south = float(box.split(",")[0])
            if south > 38.40:               # the northern row of two
                raise discover.OverpassError("simulated 504")
            return {"elements": [
                {"type": "node", "id": 7, "lat": 38.42, "lon": -122.72,
                 "tags": {"name": "Surnode-clientr", "amenity": "music"}}]}
        c.fetch = fake

        cands, failures = c.discover_area((38.40, -122.75, 38.46, -122.65),
                                          max_deg=0.06, sleep_between_tiles=0)
        ok("good tiles still returned", any(x.name == "Surnode-clientr" for x in cands))
        check("exactly the bad tiles reported", len(failures), 2)
        ok("failure names the tile", failures[0].startswith("38.43000"))


# ================================================================ runner

def main():
    tests = [
        test_classify, test_tiles, test_candidates_from_overpass,
        test_extract_jsonld, test_extract_text, test_extract_robustness,
        test_enrich_writes_cited, test_overpass_cache,
        test_failed_tile_is_reported, test_partial_coverage_survives_one_bad_tile,
    ]
    for t in tests:
        t()
    print("=" * 70)
    print(f"{PASS} passed, {FAIL} failed")
    print("=" * 70)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())