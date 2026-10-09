"""
Unit tests for timezone handling and DST transitions (Task 2.10).
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from shadenet.nightcal.tz import (
    DEFAULT_TIMEZONE,
    to_utc,
    to_utc_iso,
    to_local,
    get_tz_abbreviation,
    format_localized_time,
    normalize_event_time,
)


def test_utc_conversion_and_parsing():
    # Explicit offset timestamp
    iso_str = "2026-10-08T20:00:00-07:00"
    utc_dt = to_utc(iso_str)
    assert utc_dt.tzinfo is not None
    assert utc_dt.hour == 3  # 20 + 7 = 27 -> 03:00 next day
    assert utc_dt.day == 9
    assert to_utc_iso(iso_str) == "2026-10-09T03:00:00Z"

    # Naive timestamp assumed in DEFAULT_TIMEZONE
    naive_str = "2026-10-08T20:00:00"
    utc_from_naive = to_utc(naive_str, "America/Los_Angeles")
    assert to_utc_iso(naive_str, "America/Los_Angeles") == "2026-10-09T03:00:00Z"


def test_multi_timezone_support():
    # Same instant in UTC
    utc_iso = "2026-10-09T00:00:00Z"
    
    # In Los Angeles (PDT is UTC-7)
    la_time = format_localized_time(utc_iso, "America/Los_Angeles")
    assert la_time == "5:00 pm PDT"
    assert get_tz_abbreviation(utc_iso, "America/Los_Angeles") == "PDT"

    # In New York (EDT is UTC-4)
    ny_time = format_localized_time(utc_iso, "America/New_York")
    assert ny_time == "8:00 pm EDT"
    assert get_tz_abbreviation(utc_iso, "America/New_York") == "EDT"

    # In Chicago (CDT is UTC-5)
    chi_time = format_localized_time(utc_iso, "America/Chicago")
    assert chi_time == "7:00 pm CDT"
    assert get_tz_abbreviation(utc_iso, "America/Chicago") == "CDT"


def test_dst_spring_forward_boundary():
    """Test US Spring forward boundary on Sunday, March 8, 2026.
    At 02:00 local time, clocks spring forward to 03:00 PDT.
    Before: PST (-08:00). After: PDT (-07:00).
    """
    tz = "America/Los_Angeles"

    # 1:30 AM before transition (Standard Time)
    t_before = datetime(2026, 3, 8, 1, 30, tzinfo=ZoneInfo(tz))
    assert get_tz_abbreviation(t_before, tz) == "PST"
    assert t_before.strftime("%z") == "-0800"
    assert format_localized_time(t_before, tz) == "1:30 am PST"

    # 3:30 AM after transition (Daylight Saving Time)
    t_after = datetime(2026, 3, 8, 3, 30, tzinfo=ZoneInfo(tz))
    assert get_tz_abbreviation(t_after, tz) == "PDT"
    assert t_after.strftime("%z") == "-0700"
    assert format_localized_time(t_after, tz) == "3:30 am PDT"

    # Difference in real elapsed time in UTC is 1 hour, not 2 hours
    elapsed_seconds = (to_utc(t_after) - to_utc(t_before)).total_seconds()
    assert elapsed_seconds == 3600  # Exactly 1 hour elapsed across the spring-forward gap!


def test_dst_fall_back_boundary():
    """Test US Fall back boundary on Sunday, November 1, 2026.
    At 02:00 local time, clocks fall back to 01:00 PST.
    Before transition: PDT (-07:00). After transition: PST (-08:00).
    """
    tz = "America/Los_Angeles"

    # 12:30 AM before fallback (Daylight Time)
    t_before = datetime(2026, 11, 1, 0, 30, tzinfo=ZoneInfo(tz))
    assert get_tz_abbreviation(t_before, tz) == "PDT"
    assert t_before.strftime("%z") == "-0700"
    assert format_localized_time(t_before, tz) == "12:30 am PDT"

    # 3:30 AM after fallback (Standard Time)
    t_after = datetime(2026, 11, 1, 3, 30, tzinfo=ZoneInfo(tz))
    assert get_tz_abbreviation(t_after, tz) == "PST"
    assert t_after.strftime("%z") == "-0800"
    assert format_localized_time(t_after, tz) == "3:30 am PST"

    # Difference in real elapsed time in UTC is 4 hours, not 3 hours
    elapsed_seconds = (to_utc(t_after) - to_utc(t_before)).total_seconds()
    assert elapsed_seconds == 4 * 3600  # Exactly 4 hours elapsed across the fallback repeat!



def test_normalize_event_time_integration():
    event = {
        "id": "ev_ny_jazz",
        "title": "Brooklyn Late Night Jazz",
        "startsAt": "2026-10-08T20:00:00-04:00",
        "endsAt": "2026-10-08T23:00:00-04:00",
        "timezone": "America/New_York",
    }
    normalized = normalize_event_time(event, venue_tz="America/New_York")
    assert normalized["timezone"] == "America/New_York"
    assert normalized["tzAbbr"] == "EDT"
    assert normalized["localizedStart"] == "8:00 pm EDT"
    assert normalized["localizedEnd"] == "11:00 pm EDT"
    assert normalized["startsAtUtc"] == "2026-10-09T00:00:00Z"
