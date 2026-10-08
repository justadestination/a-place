"""Normalization: turn messy human text into comparable, storable values.

This is where most of the correctness lives. Event data arrives as:
  "Fri Mar 14, 8pm"          (venue site, no year)
  "03/14/2026 20:00"         (ticketing site, US format)
  "2026-03-14T20:00:00-08:00" (JSON-LD, fully specified)
  "Saturday, March 14th, 8:00 PM"  (a flyer transcribed by hand)
  "doors 7, show 8"          (a caption)

and all of it has to collapse to one comparable instant plus a local wall
clock, or the dedup pass fragments one show into five events and the .ics
feed puts everything at the wrong hour.

Two rules that matter more than they look:

1. **A local wall time is not a UTC instant.** A show at 8pm in Metropolis is
   8pm local on the night of the event, in Pacific time *as of that date*.
   Converting a bare "8pm" to UTC at scan time gets it wrong across DST
   boundaries. We keep the wall clock and the timezone, and convert per-event.

2. **The year is a guess until corroborated.** A December listing scanned in
   January may mean next December. We infer the year toward the near future,
   and let the corroboration pass correct it when a second source disagrees.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# Words that carry no identity. Stripped before fuzzy comparison so
# "Live at The Royal" and "The Royal" match.
_NOISE_PREFIXES = (
    "live at", "live @", "at the", "at", "the",
    "presents", "featuring", "feat", "ft", "with",
    "official", "official show", "show", "event",
)
_NOISE_SUFFIXES = (
    "(official)", "[official]", "- official", "official",
    "- live", "live", "show", "concert", "gig", "party", "event",
    "!!", "!!!", "***", "|", "-", "–", "—",
)

# Doors/show/support-act times. We keep them because "8pm" might be doors.
_TIME_IN_TEXT = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)\b", re.IGNORECASE
)
_DATE_SEP = re.compile(r"[^0-9a-zA-Z]+")


def strip_accents(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)
    )


def normalize_title(raw: str) -> str:
    """Reduce a title to a comparison key.

    Not a display title — a key. Aggressive: lowercased, de-accented,
    punctuation collapsed, noise words dropped, supporting acts moved to the
    end rather than deleted. "Foo w/ Bar" and "Bar + Foo" are the same show.
    """
    if not raw:
        return ""
    text = strip_accents(raw).lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = _DATE_SEP.sub(" ", text).strip()

    # Drop a leading date fragment ("fri mar 14", "mar 14:") up to the first
    # token that isn't a weekday/month/day marker. The date is stored
    # separately, and leaving it in makes "Mar 14: Foo" and "Mar 21: Foo" look
    # like different acts rather than the same act on different nights.
    #
    # A month token is only a month when a day number follows it. Without that
    # guard "jan" eats the start of "Jane", which is a real act name.
    text = re.sub(
        r"^(?:\s*(?:mon|tues?|wed(?:nes)?|thur?s?|fri|sat(?:ur)?|sun)(?:day|nesday)?"
        r"|\s*(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?"
        r"|jul(?:y)?|aug(?:ust)?|sep(?:t)?(?:ember)?|oct(?:ober)?|nov(?:ember)?"
        r"|dec(?:ember)?)\.?\s+\d{1,2}(?:st|nd|rd|th)?"
        r"|\s*\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?"
        r"|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t)?(?:ember)?"
        r"|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
        r"|\s*[:\-–—])+",
        "",
        text,
    ).strip()

    tokens = text.split()

    # Strip leading noise. These can be multi-word ("live at", "official
    # show"), so match against a joined prefix rather than a single token —
    # comparing tokens[0] to "live at" could never match, which is how
    # "Live at The Royal" survived a bug.
    changed = True
    while changed and tokens:
        changed = False
        for noise in _NOISE_PREFIXES:
            words = noise.split()
            if len(words) <= len(tokens) and [t.lower() for t in tokens[: len(words)]] == words:
                tokens = tokens[len(words):]
                changed = True
                break
        if not changed and tokens and tokens[0] in ("the", "at", "@"):
            tokens = tokens[1:]
            changed = True

    changed = True
    while changed and tokens:
        changed = False
        for noise in _NOISE_SUFFIXES:
            words = noise.split()
            if words and len(words) <= len(tokens) and [t.lower() for t in tokens[-len(words):]] == words:
                tokens = tokens[: len(tokens) - len(words)]
                changed = True
                break

    text = " ".join(tokens)

    # "foo w bar" / "foo with bar" / "foo + bar" -> "foo bar"
    # This must run before punctuation is stripped, and must tolerate the
    # "w/" form having already had its slash eaten by _DATE_SEP above — which
    # is why "w" appears as a standalone token here.
    text = re.sub(r"\s+(?:w|with|featuring|feat|ft|and|&|\+|x)\s+", " ", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def display_title(raw: str) -> str:
    """A presentable title, with obvious noise removed but casing kept."""
    if not raw:
        return ""
    text = re.sub(r"\s+", " ", strip_accents(raw)).strip()
    text = re.sub(r"^(?:live\s+(?:at|@)\s+|presented\s+by\s+)", "", text, flags=re.I)
    text = re.sub(r"\s*[\|\-–—]\s*(official|event)\s*$", "", text, flags=re.I)
    return text.strip()


def extract_dates(text: str) -> list[date]:
    """Pull every plausible calendar date out of a blob of text.

    Deliberately returns a list: a caption often mentions several dates
    ("playing Friday, then again on the 22nd") and we should prefer the one
    the source also gave as a machine-readable start.
    """
    if not text:
        return []
    found: list[date] = []
    lowered = strip_accents(text).lower()

    # ISO first — unambiguous, prefer it.
    for match in re.finditer(r"\b(\d{4})-(\d{2})-(\d{2})\b", text):
        try:
            found.append(date(int(match[1]), int(match[2]), int(match[3])))
        except ValueError:
            continue

    # Month-name forms: "Mar 14", "March 14th, 2026", "14 March"
    month_names = (
        "january|february|march|april|may|june|july|august|september|october"
        "|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
    )
    by_name = re.compile(
        rf"\b({month_names})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s*(\d{{4}}))?\b", re.I
    )
    for match in by_name.finditer(lowered):
        d = _build_date(match[1], match[2], match[3])
        if d:
            found.append(d)

    reverse = re.compile(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_names})\.?(?:,?\s*(\d{{4}}))?\b", re.I
    )
    for match in reverse.finditer(lowered):
        d = _build_date(match[2], match[1], match[3])
        if d:
            found.append(d)

    # Slash forms are ambiguous (US vs EU). We only accept them when the
    # first component cannot be a month, which rules out 03/14 but allows 14/3.
    slash = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
    for match in slash.finditer(text):
        a, b = int(match[1]), int(match[2])
        year = match[3]
        if a > 12 >= b:
            found.append(_safe_date(int(year) if year else None, b, a))
        elif b > 12 >= a:
            found.append(_safe_date(int(year) if year else None, a, b))

    # De-dupe, preserve order.
    seen: set[date] = set()
    out: list[date] = []
    for d in found:
        if d and d not in seen:
            seen.add(d)
            out.append(d)
    return out


_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def _build_date(month: str, day: str, year: str | None) -> date | None:
    m = _MONTHS.get(month.strip(". ").lower())
    if not m:
        return None
    return _safe_date(int(year) if year else None, m, int(day))


def _safe_date(year: int | None, month: int, day: int) -> date | None:
    if year is not None and year < 100:
        year += 2000
    try:
        if year is None:
            # Placeholder year; infer_year fixes it relative to "now".
            return date(2000, month, day)
        return date(year, month, day)
    except ValueError:
        return None


def infer_year(month: int, day: int, today: date | None = None) -> int:
    """Choose the year for a month/day with no year stated.

    Rule: pick the next occurrence. A show in December scanned in January is
    next December, not eight months ago. Allow a small grace window backwards
    so we still catch a show that happened yesterday and whose listing is
    being archived.
    """
    today = today or date.today()
    for candidate in (today.year, today.year + 1):
        try:
            d = date(candidate, month, day)
        except ValueError:
            continue
        if d >= today - timedelta(days=7):
            return candidate
    return today.year


def extract_local_time(text: str) -> tuple[int, int] | None:
    """Find an explicit clock time, if any. Returns (hour24, minute).

    Handles both 12-hour ("8pm", "8:30 PM") and 24-hour ("20:00") forms. The
    24-hour case matters for ticketing sites, which emit it consistently.
    """
    if not text:
        return None
    # 24-hour first: unambiguous, and "20:00" would otherwise be missed.
    match24 = re.search(r"\b([01]\d|2[0-3]):([0-5]\d)\b", text)
    if match24:
        return int(match24[1]), int(match24[2])

    match = _TIME_IN_TEXT.search(text)
    if not match:
        return None
    hour = int(match[1])
    minute = int(match[2] or 0)
    meridiem = match[3][0].lower()
    if meridiem == "p":
        if hour != 12:
            hour += 12
    elif meridiem == "a":
        if hour == 12:
            hour = 0
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def to_utc(
    local_date: date,
    local_time: tuple[int, int] | None,
    tz_name: str,
) -> datetime:
    """Combine a local wall clock with a timezone and convert to UTC.

    DST correctness comes free from zoneinfo: it resolves the offset for that
    specific date, so a November show and a January show get different
    offsets. A fixed -8:00 would be wrong for half the year.
    """
    hour, minute = local_time or (20, 0)  # 8pm default: most shows start then
    tz = ZoneInfo(tz_name)
    local = datetime(local_date.year, local_date.month, local_date.day, hour, minute, tzinfo=tz)
    return local.astimezone(ZoneInfo("UTC"))


def parse_start(
    *,
    iso: str | None = None,
    text: str | None = None,
    tz_name: str = "America/Los_Angeles",
    today: date | None = None,
) -> tuple[str, str, str, int, int] | None:
    """Best-effort start time from whatever the source gave us.

    Returns (utc_iso, local_date_iso, tz_name, hour, minute), or None when we
    could not find a date at all. A missing time is normal and gets a
    20:00 default — many bar listings genuinely omit it, and a wrong-but-close
    time is far more useful for dedup than no event.
    """
    if iso:
        try:
            parsed = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                # A "floating" ISO time from JSON-LD: it is local to the venue.
                local = parsed.replace(tzinfo=ZoneInfo(tz_name))
                utc = local.astimezone(ZoneInfo("UTC"))
            else:
                utc = parsed.astimezone(ZoneInfo("UTC"))
            local = utc.astimezone(ZoneInfo(tz_name))
            return (
                utc.replace(microsecond=0).isoformat(),
                local.date().isoformat(),
                tz_name,
                local.hour,
                local.minute,
            )

    candidates = extract_dates(text or "")
    if not candidates:
        return None

    for d in candidates:
        if d.year != 2000:
            chosen = d
            break
    else:
        # All candidates were year-less; infer from the first.
        d = candidates[0]
        chosen = date(infer_year(d.month, d.day, today), d.month, d.day)

    clock = extract_local_time(text or "") or (20, 0)
    utc = to_utc(chosen, clock, tz_name)
    return (
        utc.replace(microsecond=0).isoformat(),
        chosen.isoformat(),
        tz_name,
        clock[0],
        clock[1],
    )


# ---------------------------------------------------------------- performers

_BILLING_WORDS = {
    "headliner": "headline", "headline": "headline", "main": "headline",
    "support": "support", "supporting": "support", "opener": "support",
    "opening": "support", "w/": "support", "feat": "support", "featuring": "support",
    "host": "host", "dj": "support", "special guest": "support",
}


def split_performers(title: str) -> list[tuple[str, str]]:
    """Pull performer names out of a title, with billing hints.

    "Thee Oh Sees w/ Heat Sick" -> [("Thee Oh Sees", "headline"),
                                    ("Heat Sick", "support")]
    "Jane Doe & John Roe"        -> [("Jane Doe", "unknown"),
                                    ("John Roe", "unknown")]

    The last act named is the billing default, and only a marked separator
    ("w/", "with", "feat") implies support. An ampersand is just a co-headline.
    """
    if not title:
        return []
    clean = re.sub(
        r"\b(live|presents|featuring|at the|@)\b", " ", strip_accents(title), flags=re.I
    )
    clean = re.sub(r"\s+", " ", clean).strip(" -–—|")

    # Split on explicit support markers first, preserving the marker.
    parts = re.split(r"\s+(?:w/|w/ |with|featuring|feat\.?|ft\.?)\s+", clean, flags=re.I)
    parts = [p.strip(" -–—|,") for p in parts if p.strip(" -–—|,")]
    if not parts:
        return []

    results: list[tuple[str, str]] = []
    for i, part in enumerate(parts):
        sub = re.split(r"\s*(?:&|\+|/|,| x )\s*", part, flags=re.I)
        sub = [s.strip(" -–—|,") for s in sub if s.strip(" -–—|,")]
        for j, name in enumerate(sub):
            if not name or len(name) < 2:
                continue
            # Everything after an explicit support marker is support; within
            # the head segment the first name leads.
            if i > 0:
                billing = "support"
            elif j == 0 and len(sub) > 1:
                billing = "headline"
            elif j > 0:
                billing = "support"
            else:
                billing = "headline"
            results.append((name, billing))
    return results


def clean_performer_name(name: str) -> str:
    """Strip the noise that rides along with an extracted act name."""
    name = re.sub(r"\s+", " ", strip_accents(name)).strip()
    name = re.sub(
        r"^(?:live|presents|the|at)\s+", "", name, flags=re.I
    )  # only strip a leading "the" when something else remains
    name = re.sub(r"\s*(?:live|official|show|concert|set|pm|am)\s*$", "", name, flags=re.I)
    return name.strip(" -–—|,.") or name
