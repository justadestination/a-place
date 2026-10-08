"""Tests for resolve.py — the entity resolution that decides what is one event.

The two failure modes are opposite and both bad:
  * under-merge  -> calendar fills with duplicates
  * over-merge   -> a real show disappears because a different show shared
                    a similar name and time

These tests build realistic multi-source clusters and assert both directions.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from towncrier.resolve import Resolver, compare, title_similarity, venue_distance_m  # noqa: E402
from towncrier.store import Store  # noqa: E402

PASS = FAIL = 0
FAILURES: list[str] = []


def check(name: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{name}\n     got:  {got!r}\n     want: {want!r}")


def check_true(name: str, cond, detail: str = "") -> None:
    check(name if cond else f"{name} [{detail}]", bool(cond), True)


# ------------------------------------------------------------ title similarity

check("exact title", title_similarity("foo bar", "foo bar"), 100.0)
check_true(
    "billing order irrelevant",
    title_similarity("foo bar", "bar foo") >= 99.0,
    str(title_similarity("foo bar", "bar foo")),
)
check_true("subset title scores high", title_similarity("foo", "foo bar") >= 78.0)
# Two unrelated short strings still share a nonzero character-similarity floor
# (equal-length strings score ~22 regardless of content), so "low" means
# "far below any merge threshold" rather than literally zero.
check_true(
    "disjoint titles score far below merge threshold",
    title_similarity("alpha", "zulu") < 40.0,
    str(title_similarity("alpha", "zulu")),
)
check("empty is 0", title_similarity("", "foo"), 0.0)
check_true(
    "typo still matches",
    title_similarity("thee oh sees", "thee oh seez") >= 85.0,
    str(title_similarity("thee oh sees", "thee oh seez")),
)
check_true(
    "different bands stay apart",
    title_similarity("thee oh sees", "fela kuti") < 78.0,
    str(title_similarity("thee oh sees", "fela kuti")),
)

# ------------------------------------------------------------ geo distance

d = venue_distance_m(37.7740, -122.4194, 37.7741, -122.4195)
check_true("same-ish coords are close", d is not None and d < 100, str(d))
d_far = venue_distance_m(37.7740, -122.4194, 34.0522, -118.2437)
check_true("SR to LA is far", d_far is not None and d_far > 500_000, str(d_far))
check("missing coords -> None", venue_distance_m(None, None, 1.0, 1.0), None)


# ------------------------------------------------------------ full pipeline

def build_store() -> Store:
    tmp = tempfile.mkdtemp(prefix="towncrier-test-")
    return Store(Path(tmp) / "test.db")


def add_listing(store: Store, *, source, ext, title, norm, starts, venue_id,
                venue_name="The Royal", status="EventScheduled", desc=None):
    return store.upsert_listing(
        source_id=source, external_id=ext, url=f"https://x.test/{ext}",
        title_raw=title, title_norm=norm, starts_at=starts,
        ends_at=None, status=status, venue_id=venue_id,
        venue_name_raw=venue_name, description=desc,
    )


store = build_store()
store.upsert_source("venue_site", "jsonld")
store.upsert_source("ticketing", "api")
store.upsert_source("promoter", "manual")

royal = store.ensure_venue("The Royal", city="Metropolis", lat=37.7740, lon=-122.4194)
other = store.ensure_venue("Other Club", city="Metropolis", lat=37.7800, lon=-122.4100)

# The same show, described four ways. Note the title variations, the billing
# order flip, and the 30-minute start disagreement (doors vs show).
add_listing(store, source="venue_site", ext="v1",
            title="Thee Oh Sees w/ Heat Sick", norm="thee oh sees heat sick",
            starts="2026-07-10T20:00:00+00:00", venue_id=royal)
add_listing(store, source="ticketing", ext="t1",
            title="Heat Sick + Thee Oh Sees", norm="heat sick thee oh sees",
            starts="2026-07-10T20:30:00+00:00", venue_id=royal)
add_listing(store, source="promoter", ext="p1",
            title="Thee Oh Sees with Heat Sick", norm="thee oh sees heat sick",
            starts="2026-07-10T20:00:00+00:00", venue_id=royal,
            desc="Doors 7pm. All ages.")

# A genuinely different show the same night, same venue — must NOT merge.
add_listing(store, source="venue_site", ext="v2",
            title="Special", norm="special",
            starts="2026-07-10T22:00:00+00:00", venue_id=royal)

# A different venue entirely.
add_listing(store, source="ticketing", ext="t2",
            title="Fela Kuti Tribute", norm="fela kuti tribute",
            starts="2026-07-10T20:00:00+00:00", venue_id=other)

resolver = Resolver(store)
summary = resolver.resolve()

check("all listings stored", summary["listings"], 5)
check("clusters formed", summary["events"], 3)

events = store.query("SELECT * FROM events ORDER BY title_norm")
titles = sorted(e["title_norm"] for e in events)
check(
    "cluster identities",
    titles,
    ["fela kuti tribute", "special", "thee oh sees heat sick"],
)

merged = next((e for e in events if e["title_norm"] == "thee oh sees heat sick"), None)
check_true("Oh Sees cluster exists", merged is not None)
assert merged is not None, "Oh Sees cluster missing"
check("three listings merged into one", merged["listing_count"], 3)
check("corroboration counts distinct sources", merged["source_count"], 3)
check_true(
    "merged event is high confidence",
    merged["confidence"] >= 0.85,
    str(merged["confidence"]),
)
check_true("merged event clears review", merged["needs_review"] == 0,
           f"needs_review={merged['needs_review']} reason={merged['review_reason']}")

# The two 20:00 shows at different venues must stay separate.
special = next((e for e in events if e["title_norm"] == "special"), None)
check_true("same-title different-time stays separate", special is not None)
if special:
    check("special is a singleton", special["listing_count"], 1)
    check("singleton has one source", special["source_count"], 1)

fela = next((e for e in events if e["title_norm"] == "fela kuti tribute"), None)
check_true("different venue stays separate", fela is not None)
if fela:
    check("fela is a singleton", fela["listing_count"], 1)

# Performers linked from titles.
pers = store.query(
    """SELECT p.name, ep.billing FROM event_performers ep
       JOIN performers p ON p.id = ep.performer_id
       JOIN events e ON e.id = ep.event_id
       WHERE e.title_norm = 'thee oh sees heat sick'"""
)
pers_names = sorted(p["name"] for p in pers)
check("both acts extracted", pers_names, ["Heat Sick", "Thee Oh Sees"])
billing = {p["name"]: p["billing"] for p in pers}
check("headline billing", billing.get("Thee Oh Sees"), "headline")
check("support billing", billing.get("Heat Sick"), "support")

# ------------------------------------------------------------ idempotency
before = store.query("SELECT id, listing_count, source_count FROM events ORDER BY id")
resolver.resolve()
after = store.query("SELECT id, listing_count, source_count FROM events ORDER BY id")
check(
    "re-resolve is stable",
    [tuple(r) for r in before],
    [tuple(r) for r in after],
)
check(
    "re-resolve keeps current shows active",
    [row["active"] for row in store.query("SELECT active FROM events ORDER BY id")],
    [1] * len(before),
)

# ------------------------------------------------------------ cancellation
store2 = build_store()
store2.upsert_source("venue_site", "jsonld")
store2.upsert_source("ticketing", "api")
r2 = store2.ensure_venue("The Royal")
add_listing(store2, source="venue_site", ext="v1", title="Foo", norm="foo",
            starts="2026-07-10T20:00:00+00:00", venue_id=r2)
add_listing(store2, source="ticketing", ext="t1", title="Foo", norm="foo",
            starts="2026-07-10T20:00:00+00:00", venue_id=r2)
Resolver(store2).resolve()
eid = store2.query("SELECT id FROM events")[0]["id"]
check("pre-cancel review flag", store2.get_event(eid)["needs_review"], 0)

# Venue site cancels; ticketing site has not caught up yet.
add_listing(store2, source="venue_site", ext="v1", title="Foo", norm="foo",
            starts="2026-07-10T20:00:00+00:00", venue_id=r2,
            status="EventCancelled")
Resolver(store2).resolve()
ev = store2.get_event(eid)
check("cancellation is sticky across sources", ev["status"], "EventCancelled")
check("cancelled_at stamped", bool(ev["cancelled_at"]), True)
check("change recorded", store2.one(
    "SELECT COUNT(*) c FROM event_changes WHERE event_id=? AND field='status'", (eid,)
)["c"] >= 1, True)
# Single-source cancellation is held for review, since a venue rotating its
# calendar looks identical to a cancellation.
check("single-source cancel held for review", ev["needs_review"], 1)

# Once the second source also cancels, it publishes.
add_listing(store2, source="ticketing", ext="t1", title="Foo", norm="foo",
            starts="2026-07-10T20:00:00+00:00", venue_id=r2,
            status="EventCancelled")
Resolver(store2).resolve()
ev2 = store2.get_event(eid)
check("corroborated cancel publishes", ev2["needs_review"], 0)
check("still cancelled", ev2["status"], "EventCancelled")

# ------------------------------------------------------------ retraction
store3 = build_store()
store3.upsert_source("venue_site", "jsonld")
r3 = store3.ensure_venue("The Royal")
add_listing(store3, source="venue_site", ext="v1", title="Solo Show", norm="solo show",
            starts="2026-08-01T20:00:00+00:00", venue_id=r3)
Resolver(store3).resolve()
eid3 = store3.query("SELECT id FROM events")[0]["id"]
conf_before = store3.get_event(eid3)["confidence"]

gone = store3.mark_listings_missing("venue_site", set(), "not in feed")
check("retraction detected", len(gone), 1)
Resolver(store3).resolve()
conf_after = store3.get_event(eid3)["confidence"]
check_true(
    "retraction lowers confidence",
    conf_after < conf_before,
    f"{conf_before} -> {conf_after}",
)
check(
    "retracted listing is not deleted",
    store3.one("SELECT COUNT(*) c FROM listings WHERE missing_since IS NOT NULL")["c"],
    1,
)

# ------------------------------------------------------------ compare() unit


class R:
    """Minimal stand-in exposing the fields compare() reads."""

    def __init__(self, **kw):
        self.id = kw.get("id", 0)
        self.title_norm = kw.get("title_norm", "")
        self.starts_at = kw.get("starts_at")
        self.venue_id = kw.get("venue_id")
        self.venue_name_raw = kw.get("venue_name_raw", "")

    def __getitem__(self, k):
        return getattr(self, k)


m = compare(
    R(id=1, title_norm="foo bar", starts_at="2026-07-10T20:00:00+00:00", venue_id="v1"),
    R(id=2, title_norm="foo bar", starts_at="2026-07-10T20:00:00+00:00", venue_id="v1"),
)
check("same title/time/venue merges", m.merged, True)

m = compare(
    R(id=1, title_norm="foo bar", starts_at="2026-07-10T20:00:00+00:00", venue_id="v1"),
    R(id=2, title_norm="bar baz", starts_at="2026-07-10T20:00:00+00:00", venue_id="v1"),
)
check("different titles same slot do not merge", m.merged, False)

m = compare(
    R(id=1, title_norm="foo bar", starts_at="2026-07-10T20:00:00+00:00", venue_id="v1"),
    R(id=2, title_norm="foo bar", starts_at="2026-07-10T20:00:00+00:00", venue_id="v2"),
)
check("same title/time different venue does not merge", m.merged, False)
check_true("declined cross-venue merge explains itself", "different venue" in m.reason, m.reason)

m = compare(
    R(id=1, title_norm="foo bar", starts_at="2026-07-10T20:00:00+00:00", venue_id=None,
      venue_name_raw="The Royal"),
    R(id=2, title_norm="foo bar", starts_at="2026-07-10T20:00:00+00:00", venue_id=None,
      venue_name_raw="The Royal"),
)
check("venue matched by name when no id", m.merged, True)

m = compare(
    R(id=1, title_norm="foo", starts_at=None, venue_id=None, venue_name_raw="Royal"),
    R(id=2, title_norm="foo", starts_at=None, venue_id=None, venue_name_raw="Royal"),
)
check("undated but same venue+title merges", m.merged, True)

m = compare(
    R(id=1, title_norm="foo", starts_at=None, venue_id=None, venue_name_raw="Royal"),
    R(id=2, title_norm="bar", starts_at=None, venue_id=None, venue_name_raw="Royal"),
)
check("undated + different title does not merge", m.merged, False)

# ------------------------------------------------------------ summary

print("=" * 70)
print("RESOLVE TESTS")
print("=" * 70)
for f in FAILURES:
    print(f"  FAIL  {f}")
print("-" * 70)
print(f"{PASS} passed, {FAIL} failed")
print("=" * 70)

sys.exit(1 if FAIL else 0)
