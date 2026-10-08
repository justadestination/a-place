"""Parse the Downtown Metropolis public events calendar.

The page is server-rendered cards, not schema.org. Each card is one
listing: a title, a clock range, a venue when they printed one, and
either a single day or a start/end pair. Nothing in here invents a
field the card did not contain.
"""

from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta

from towncrier.normalize import clean_performer_name, split_performers

DAO_ORIGIN = "https://www.downtownsantarosa.org"

_CARD = re.compile(
    r'<a class="evcard" href="([^"]+)">(.*?)</a>',
    re.S,
)
_HEAD = re.compile(r'class="evcard-content-headline">([^<]+)')
_SUB = re.compile(r'class="evcard-content-subhead[^"]*">([^<]+)')
_TIME = re.compile(r'class="evcard-content-time">.*?</span>\s*([^<]+)', re.S)
_VENUE = re.compile(r'class="evcard-content-venue">.*?</span>\s*([^<]+)', re.S)
_IMG = re.compile(r'data-src="([^"]+)"')
_DAY = re.compile(r'class="evcard-date-day">([^<]+)')
_MONTH = re.compile(r'class="evcard-date-month">([^<]+)')
_RANGE_DAY = re.compile(
    r'class="evcard-date-range">\s*([A-Za-z]+)\s*<span>(\d+)</span>'
)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Series names the downtown calendar prints in front of the act.
_SERIES = (
    r"^Main Street Sessions:\s*",
    r"^Downtown Sound:\s*",
    r"^Headline Comedy\s*[-–—]\s*",
    r"^Pro Jam\s*[-–—]\s*(?:with special guest\s*)?",
)

_SKIP_ACTS = {
    "tbd", "tba", "downtown metropolis", "main street tavern", "main street sessions",
}


def _text(fragment: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", fragment)).strip()


def _month_num(token: str) -> int | None:
    return _MONTHS.get(token.strip()[:3].lower())


def _year_for(month: int, today: date) -> int:
    """A November card read in October is this year; a January card is next."""
    year = today.year
    if month < today.month - 1:
        year += 1
    return year


def _clock(token: str) -> tuple[int, int] | None:
    match = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", token.strip(), re.I)
    if not match:
        return None
    hour = int(match.group(1)) % 12
    if match.group(3).lower() == "pm":
        hour += 12
    return hour, int(match.group(2) or 0)


def parse_time_range(raw: str) -> tuple[tuple[int, int] | None, tuple[int, int] | None]:
    parts = re.split(r"\s*[–—-]\s*", raw.strip(), maxsplit=1)
    start = _clock(parts[0]) if parts and parts[0] else None
    end = _clock(parts[1]) if len(parts) > 1 else None
    return start, end


def parse_cards(page: str, *, today: date | None = None) -> list[dict]:
    """Return one dict per event card. Dates are local calendar dates."""
    today = today or date.today()
    listings: list[dict] = []
    for href, body in _CARD.findall(page):
        title_m = _HEAD.search(body)
        if not title_m:
            continue
        title = _text(title_m.group(1))
        sub = _text(_SUB.search(body).group(1)) if _SUB.search(body) else ""
        categories = [c.strip() for c in sub.split("•") if c.strip()]
        if not categories and sub:
            categories = [sub]
        time_raw = _text(_TIME.search(body).group(1)) if _TIME.search(body) else ""
        venue = _text(_VENUE.search(body).group(1)) if _VENUE.search(body) else ""
        if not venue and any(c.lower() == "main street tavern" for c in categories):
            venue = "Main Street Tavern"
        image_m = _IMG.search(body)
        image = html.unescape(image_m.group(1)) if image_m else ""

        range_days = _RANGE_DAY.findall(body)
        if range_days:
            start_month = _month_num(range_days[0][0])
            start_day = int(range_days[0][1])
            end_month = _month_num(range_days[-1][0])
            end_day = int(range_days[-1][1])
        else:
            day_m = _DAY.search(body)
            month_m = _MONTH.search(body)
            if not day_m or not month_m:
                continue
            start_month = end_month = _month_num(month_m.group(1))
            start_day = end_day = int(day_m.group(1))
        if not start_month or not end_month:
            continue

        start_date = date(_year_for(start_month, today), start_month, start_day)
        end_date = date(_year_for(end_month, today), end_month, end_day)
        if end_date < start_date:
            end_date = date(end_date.year + 1, end_date.month, end_date.day)

        start_clock, end_clock = parse_time_range(time_raw)
        end_on = end_date
        if start_clock and end_clock and end_date == start_date:
            if (end_clock[0], end_clock[1]) <= (start_clock[0], start_clock[1]):
                end_on = start_date + timedelta(days=1)

        path = href if href.startswith("/") else "/" + href
        listings.append({
            "title": title,
            "categories": categories,
            "kind": classify_kind(categories, title),
            "time_raw": time_raw,
            "start_clock": start_clock,
            "end_clock": end_clock,
            "start_date": start_date,
            "end_date": end_on,
            "venue": venue,
            "image": image if image.startswith("https://") else "",
            "path": path,
            "url": DAO_ORIGIN + path,
        })
    return listings


def classify_kind(categories: list[str], title: str) -> str:
    blob = " ".join(categories).lower()
    title_l = title.lower()
    if "live music" in blob or "concert" in blob:
        return "music"
    if "comedy" in blob:
        return "comedy"
    if "theater" in blob or "theatre" in blob:
        return "show"
    if "trivia" in blob:
        return "trivia"
    if "food truck" in title_l:
        return "trucks"
    if "market" in blob or "market" in title_l:
        return "market"
    return "other"


def acts_from_title(title: str, venue: str = "") -> list[tuple[str, str]]:
    """Act names stated in a listing title, with a billing hint.

    Only splits on words the title actually uses ("opens for", "with").
    A title that is just a long description comes back empty rather than
    being filed as a band.
    """
    text = title.strip()
    for pattern in _SERIES:
        text = re.sub(pattern, "", text, flags=re.I)
    text = re.sub(r"\s+in Downtown Metropolis\s*$", "", text, flags=re.I)
    if venue:
        text = re.sub(
            rf"\s+at\s+{re.escape(venue)}\s*$", "", text, flags=re.I
        )
    text = text.strip(" -–—")

    opener = re.split(r"\s+opens for\s+", text, maxsplit=1, flags=re.I)
    if len(opener) == 2:
        pairs = [(opener[0], "support"), (opener[1], "headline")]
    else:
        if "!" in text:
            head = text.split("!", 1)[0].strip()
            if 1 < len(head) <= 40:
                text = head
        pairs = split_performers(text)

    acts: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name, billing in pairs:
        cleaned = clean_performer_name(name)
        key = cleaned.lower()
        if not cleaned or key in _SKIP_ACTS or key in seen:
            continue
        if len(cleaned) > 42:
            continue
        if "food truck" in key or key.endswith(" market") or key.endswith(" markets"):
            continue
        if venue and key == venue.lower():
            continue
        seen.add(key)
        acts.append((cleaned, billing))
    return acts


def combine_local(day: date, clock: tuple[int, int] | None) -> datetime | None:
    if clock is None:
        return None
    return datetime(day.year, day.month, day.day, clock[0], clock[1])
