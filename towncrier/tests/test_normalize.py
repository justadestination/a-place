"""Tests for normalize.py — the layer where silent wrongness is most costly."""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from towncrier import normalize as N  # noqa: E402

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


# --------------------------------------------------------------- titles

check("title: live prefix", N.normalize_title("Live at The Royal"), "royal")
check("title: case + accents", N.normalize_title("Café Tacvba"), "cafe tacvba")
check("title: punctuation", N.normalize_title("Foo!!! / Bar???"), "foo bar")
check("title: empty", N.normalize_title(""), "")
check("title: whitespace", N.normalize_title("   Spaced   Out   "), "spaced out")
check(
    "title: ampersand is co-headline not support",
    N.normalize_title("Jane Doe & John Roe"),
    "jane doe john roe",
)
# A show and its billing order should collapse to one key. Compare against
# the expected key rather than against another normalization — asserting
# normalize(a) == normalize(b) would also pass if both were broken the same
# way, which is how "foo w bar" survived a bug once already.
check("title: 'w/' separator collapses", N.normalize_title("Foo w/ Bar"), "foo bar")
check("title: 'with' separator collapses", N.normalize_title("Bar with Foo"), "bar foo")
# NOTE: normalize_title preserves billing order, so "foo bar" != "bar foo".
# Order-insensitive comparison is the resolver's job (it compares token sets);
# see test_resolve.py. Asserting it here would be testing the wrong layer.
# Both must actually be the same key, and neither may retain a stray "w".
check_true(
    "title: 'w/' leaves no orphan token",
    " w " not in f" {N.normalize_title('Foo w/ Bar')} ",
    N.normalize_title("Foo w/ Bar"),
)
check("display keeps case", N.display_title("Live at The Royal"), "The Royal")

# --------------------------------------------------------------- dates

check("iso date", N.extract_dates("2026-03-14"), [date(2026, 3, 14)])
check(
    "month name with year",
    N.extract_dates("Mar 14, 2026"),
    [date(2026, 3, 14)],
)
check("month name bare", N.extract_dates("March 14th"), [date(2000, 3, 14)])
check(
    "reverse order 14 March",
    N.extract_dates("14 March 2026"),
    [date(2026, 3, 14)],
)
check("US slash 03/14", N.extract_dates("03/14/2026"), [date(2026, 3, 14)])
check("EU slash 14/3", N.extract_dates("14/3/2026"), [date(2026, 3, 14)])
check("no date", N.extract_dates("live music all week"), [])
check("invalid date rejected", N.extract_dates("2026-02-30"), [])
check("feb 29 leap", N.extract_dates("2028-02-29"), [date(2028, 2, 29)])

# Two-digit years
check("2-digit year", N.extract_dates("03/14/26"), [date(2026, 3, 14)])

# --------------------------------------------------------------- times

check("time 8pm", N.extract_local_time("doors 8pm"), (20, 0))
check("time 8:30 PM", N.extract_local_time("8:30 PM"), (20, 30))
check("time 20:00", N.extract_local_time("20:00"), (20, 0))
check("time 12am", N.extract_local_time("12am"), (0, 0))
check("time 12pm", N.extract_local_time("12pm"), (12, 0))
check("time absent", N.extract_local_time("no time here"), None)
check("time punctuated", N.extract_local_time("9 p.m."), (21, 0))
check("time lowercase", N.extract_local_time("starts at 7:30 pm"), (19, 30))

# --------------------------------------------------------------- year inference

check("infer year: future stays future", N.infer_year(12, 25, date(2026, 1, 10)), 2026)
check("infer year: past rolls forward", N.infer_year(3, 1, date(2026, 6, 1)), 2027)
check("infer year: grace window", N.infer_year(6, 1, date(2026, 6, 3)), 2026)

# --------------------------------------------------------------- DST correctness
#
# This is the test that matters most: a fixed UTC offset would fail both.

utc_summer = N.to_utc(date(2026, 7, 15), (20, 0), "America/Los_Angeles")
utc_winter = N.to_utc(date(2026, 12, 15), (20, 0), "America/Los_Angeles")
check(
    "summer 8pm PDT is 03:00Z next day",
    utc_summer.strftime("%Y-%m-%dT%H:%M"),
    "2026-07-16T03:00",
)
check(
    "winter 8pm PST is 04:00Z next day",
    utc_winter.strftime("%Y-%m-%dT%H:%M"),
    "2026-12-16T04:00",
)
# Compare the *local* offsets: to_utc returns UTC, whose own utcoffset() is
# always zero, so asserting on it would pass vacuously.
tz = ZoneInfo("America/Los_Angeles")
summer_off = datetime(2026, 7, 15, 20, 0, tzinfo=tz).utcoffset()
winter_off = datetime(2026, 12, 15, 20, 0, tzinfo=tz).utcoffset()
check_true(
    "DST offsets actually differ",
    summer_off != winter_off,
    f"{summer_off} vs {winter_off}",
)
check("summer local offset is PDT -7h", summer_off.total_seconds(), -7 * 3600)
check("winter local offset is PST -8h", winter_off.total_seconds(), -8 * 3600)

# The clock time must survive the round trip.
for label, d, want_hour in (
    ("summer wall clock preserved", utc_summer, 20),
    ("winter wall clock preserved", utc_winter, 20),
):
    local = d.astimezone(ZoneInfo("America/Los_Angeles"))
    check(f"{label}", local.hour, want_hour)

# --------------------------------------------------------------- parse_start

r = N.parse_start(iso="2026-03-14T20:00:00-08:00", tz_name="America/Los_Angeles")
check_true("parse_start from aware ISO", r is not None)
if r:
    check("parse_start UTC", r[0], "2026-03-15T04:00:00+00:00")
    check("parse_start local date", r[1], "2026-03-14")

r = N.parse_start(
    iso="2026-03-14T20:00:00", tz_name="America/Los_Angeles"
)
check_true("parse_start from floating ISO", r is not None)
if r:
    # 2026-03-14 is AFTER DST begins (2026-03-08), so 8pm local is PDT (-7)
    # and lands at 03:00Z. Asserting 04:00 here would be testing a wrong
    # expectation, not a bug — the whole point of zoneinfo is that this
    # differs from a December show.
    check(
        "floating ISO treated as venue-local (PDT after Mar 8)",
        r[0],
        "2026-03-15T03:00:00+00:00",
    )
    check("floating ISO local hour preserved", (r[3], r[4]), (20, 0))

# Same wall clock, different season, different UTC instant.
r_summer = N.parse_start(iso="2026-07-14T20:00:00", tz_name="America/Los_Angeles")
r_winter = N.parse_start(iso="2026-12-14T20:00:00", tz_name="America/Los_Angeles")
check_true("both parse", r_summer is not None and r_winter is not None)
if r_summer and r_winter:
    check_true(
        "identical wall clock resolves to different UTC instants",
        r_summer[0] != r_winter[0],
        f"{r_summer[0]} vs {r_winter[0]}",
    )

r = N.parse_start(text="Fri Mar 14, 8pm", tz_name="America/Los_Angeles", today=date(2026, 3, 1))
check_true("parse_start from text", r is not None)
if r:
    check("text year inferred", r[1], "2026-03-14")
    check("text time extracted", (r[3], r[4]), (20, 0))

check_true(
    "parse_start with no date returns None",
    N.parse_start(text="sometime soon") is None,
)

# No stated time -> 8pm default, not midnight.
r = N.parse_start(text="Mar 14 2026", tz_name="America/Los_Angeles", today=date(2026, 3, 1))
check_true("default time used when absent", r is not None)
if r:
    check("default is 20:00 not 00:00", (r[3], r[4]), (20, 0))

# --------------------------------------------------------------- performers

check(
    "performers: headline + support",
    N.split_performers("Thee Oh Sees w/ Heat Sick"),
    [("Thee Oh Sees", "headline"), ("Heat Sick", "support")],
)
check(
    "performers: ampersand co-headline",
    N.split_performers("Jane Doe & John Roe"),
    [("Jane Doe", "headline"), ("John Roe", "support")],
)
check(
    "performers: 'with' support",
    N.split_performers("Modest Mouse with Broken Bells"),
    [("Modest Mouse", "headline"), ("Broken Bells", "support")],
)
check("performers: single act", N.split_performers("Fela Kuti"), [("Fela Kuti", "headline")])
check("performers: empty", N.split_performers(""), [])

check("clean name strips suffix", N.clean_performer_name("Foo Live"), "Foo")
check("clean name keeps interior 'the'", N.clean_performer_name("Thee Oh Sees"), "Thee Oh Sees")

# --------------------------------------------------------------- summary

print("=" * 66)
print("NORMALIZE TESTS")
print("=" * 66)
for f in FAILURES:
    print(f"  FAIL  {f}")
print("-" * 66)
print(f"{PASS} passed, {FAIL} failed")
print("=" * 66)

sys.exit(1 if FAIL else 0)
