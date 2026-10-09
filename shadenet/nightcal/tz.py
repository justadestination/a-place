"""
shadenet.nightcal.tz — Timezone-aware timestamp handling and localization (Task 2.10).

Ensures:
  1. Stored in UTC or venue-local with explicit ISO offset.
  2. Rendered in venue-local time everywhere.
  3. Supports venues outside Santa Rosa (multi-timezone support).
  4. Formats localized times with standard timezone abbreviations (e.g. '8:00 pm PDT' vs '8:00 pm EDT').
  5. Accurate DST boundary transitions (Spring forward / Fall back).
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any

DEFAULT_TIMEZONE = "America/Los_Angeles"


def get_zone(tz_name: str | None = None) -> ZoneInfo:
    """Return ZoneInfo for the given name or default Santa Rosa timezone."""
    if not tz_name or not tz_name.strip():
        tz_name = DEFAULT_TIMEZONE
    try:
        return ZoneInfo(tz_name.strip())
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


def parse_datetime(dt_val: str | datetime, tz_name: str | None = None) -> datetime:
    """Parse string or datetime to timezone-aware datetime.
    
    If dt_val is naive, localizes it to tz_name (or DEFAULT_TIMEZONE).
    If dt_val has explicit offset/tz, preserves the instant.
    """
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            return dt_val.replace(tzinfo=get_zone(tz_name))
        return dt_val

    raw = str(dt_val).strip()
    # Normalize trailing Z to +00:00 for fromisoformat compatibility
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"

    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=get_zone(tz_name))
    return dt


def to_utc(dt_val: str | datetime, tz_name: str | None = None) -> datetime:
    """Convert any timestamp to UTC datetime."""
    dt = parse_datetime(dt_val, tz_name)
    return dt.astimezone(timezone.utc)


def to_utc_iso(dt_val: str | datetime, tz_name: str | None = None) -> str:
    """Convert to standard ISO 8601 UTC string (ending in Z)."""
    utc_dt = to_utc(dt_val, tz_name)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def to_local(dt_val: str | datetime, tz_name: str | None = None) -> datetime:
    """Convert timestamp to venue-local datetime."""
    dt = parse_datetime(dt_val, tz_name)
    target_zone = get_zone(tz_name)
    return dt.astimezone(target_zone)


def get_tz_abbreviation(dt_val: str | datetime, tz_name: str | None = None) -> str:
    """Return localized timezone abbreviation, e.g. 'PDT', 'PST', 'EDT', 'EST'."""
    local_dt = to_local(dt_val, tz_name)
    tzname = local_dt.tzname()
    if tzname:
        return tzname
    # Fallback to offset format if abbreviation unavailable
    offset = local_dt.strftime("%z")
    return f"UTC{offset[:3]}:{offset[3:]}" if offset else "UTC"


def format_localized_time(
    dt_val: str | datetime,
    tz_name: str | None = None,
    include_tz: bool = True
) -> str:
    """Format localized time string, e.g. '8:00 pm PDT' or '11:30 am EDT'.
    
    Uses 12-hour clock with lowercase am/pm and optional timezone abbreviation.
    """
    local_dt = to_local(dt_val, tz_name)
    # Format hour (1-12)
    hour = local_dt.hour % 12
    if hour == 0:
        hour = 12
    minute = f"{local_dt.minute:02d}"
    ampm = "am" if local_dt.hour < 12 else "pm"
    time_str = f"{hour}:{minute} {ampm}"
    if include_tz:
        abbr = get_tz_abbreviation(local_dt, tz_name)
        return f"{time_str} {abbr}"
    return time_str


def normalize_event_time(event: dict[str, Any], venue_tz: str | None = None) -> dict[str, Any]:
    """Ensure event startsAt/endsAt are timezone-aware and annotated with localized display."""
    res = dict(event)
    tz = venue_tz or event.get("timezone") or DEFAULT_TIMEZONE
    
    starts_at = event.get("startsAt")
    if starts_at:
        local_start = to_local(starts_at, tz)
        res["startsAtUtc"] = to_utc_iso(starts_at, tz)
        res["startsAtLocal"] = local_start.isoformat()
        res["timezone"] = tz
        res["tzAbbr"] = get_tz_abbreviation(local_start, tz)
        res["localizedStart"] = format_localized_time(local_start, tz, include_tz=True)
        
    ends_at = event.get("endsAt")
    if ends_at:
        local_end = to_local(ends_at, tz)
        res["endsAtUtc"] = to_utc_iso(ends_at, tz)
        res["endsAtLocal"] = local_end.isoformat()
        res["localizedEnd"] = format_localized_time(local_end, tz, include_tz=True)

    return res
