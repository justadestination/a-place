"""Unit and integration tests for Task 2.9: Event lifecycle.

Verifies:
  1. Clock-freeze transitions: upcoming -> happening_now -> past/archived.
  2. Default event duration fallback when endsAt is not specified.
  3. Recurring events multi-week expansion across three weeks (weekly residencies).
  4. Active vs archived events filtering.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import pytest

from shadenet.nightcal.lifecycle import (
    compute_event_lifecycle,
    expand_recurring_events,
    filter_archived_events,
    parse_datetime,
)

LA = ZoneInfo("America/Los_Angeles")


def test_clock_freeze_transitions():
    # Show starts at 8:00 PM and ends at 11:00 PM on October 9, 2026
    start_str = "2026-10-09T20:00:00-07:00"
    end_str = "2026-10-09T23:00:00-07:00"

    # 1. Clock freeze: 7:59 PM (1 minute before start) -> Upcoming
    t_before = datetime(2026, 10, 9, 19, 59, 0, tzinfo=LA)
    lc_before = compute_event_lifecycle(start_str, end_str, now=t_before)
    assert lc_before["state"] == "upcoming"
    assert lc_before["happening_now"] is False
    assert lc_before["is_past"] is False
    assert lc_before["is_archived"] is False

    # 2. Clock freeze: 8:00 PM exact start -> Happening now
    t_start = datetime(2026, 10, 9, 20, 0, 0, tzinfo=LA)
    lc_start = compute_event_lifecycle(start_str, end_str, now=t_start)
    assert lc_start["state"] == "happening_now"
    assert lc_start["happening_now"] is True
    assert lc_start["is_past"] is False
    assert lc_start["is_archived"] is False

    # 3. Clock freeze: 9:30 PM (midway through show) -> Happening now
    t_mid = datetime(2026, 10, 9, 21, 30, 0, tzinfo=LA)
    lc_mid = compute_event_lifecycle(start_str, end_str, now=t_mid)
    assert lc_mid["state"] == "happening_now"
    assert lc_mid["happening_now"] is True
    assert lc_mid["is_past"] is False

    # 4. Clock freeze: 11:00 PM exact end -> Happening now (inclusive)
    t_end = datetime(2026, 10, 9, 23, 0, 0, tzinfo=LA)
    lc_end = compute_event_lifecycle(start_str, end_str, now=t_end)
    assert lc_end["state"] == "happening_now"
    assert lc_end["happening_now"] is True
    assert lc_end["is_past"] is False

    # 5. Clock freeze: 11:01 PM (1 minute after end) -> Past / Archived
    t_past = datetime(2026, 10, 9, 23, 1, 0, tzinfo=LA)
    lc_past = compute_event_lifecycle(start_str, end_str, now=t_past)
    assert lc_past["state"] == "past"
    assert lc_past["happening_now"] is False
    assert lc_past["is_past"] is True
    assert lc_past["is_archived"] is True


def test_default_duration_fallback():
    # Start at 7:00 PM with no end time specified (defaults to +3 hours = 10:00 PM)
    start_str = "2026-10-09T19:00:00-07:00"

    # At 9:30 PM (+2.5 hours) -> happening now
    now_during = datetime(2026, 10, 9, 21, 30, 0, tzinfo=LA)
    lc_during = compute_event_lifecycle(start_str, ends_at=None, now=now_during, default_duration_hours=3.0)
    assert lc_during["state"] == "happening_now"
    assert lc_during["happening_now"] is True

    # At 10:05 PM (+3 hours 5 min) -> past
    now_after = datetime(2026, 10, 9, 22, 5, 0, tzinfo=LA)
    lc_after = compute_event_lifecycle(start_str, ends_at=None, now=now_after, default_duration_hours=3.0)
    assert lc_after["state"] == "past"
    assert lc_after["is_past"] is True


def test_recurring_events_multi_week_expansion():
    # Seeded weekly residency on Thursday
    base_event = {
        "id": "residency-jazz-thursday",
        "title": "Downtown Jazz Jam Residency",
        "date": "2026-10-08",
        "startsAt": "2026-10-08T20:00:00-07:00",
        "endsAt": "2026-10-08T23:00:00-07:00",
        "venue": "Arlene Francis Center",
        "venueId": "afc",
        "kind": "music",
        "isRecurring": True,
        "recurrence": "weekly",
        "bodies": 150,
    }

    # Expand across 3 weeks (2026-10-08 to 2026-10-25)
    expanded = expand_recurring_events([base_event], start_date="2026-10-08", end_date="2026-10-25")

    # Assert exactly 3 occurrences generated
    assert len(expanded) == 3

    occ1 = expanded[0]
    assert occ1["date"] == "2026-10-08"
    assert occ1["id"] == "residency-jazz-thursday"
    assert occ1["startsAt"] == "2026-10-08T20:00:00-07:00"

    occ2 = expanded[1]
    assert occ2["date"] == "2026-10-15"
    assert occ2["id"] == "residency-jazz-thursday_occ_2026-10-15"
    assert occ2["startsAt"] == "2026-10-15T20:00:00-07:00"
    assert occ2["endsAt"] == "2026-10-15T23:00:00-07:00"
    assert occ2["isRecurring"] is True
    assert occ2["baseEventId"] == "residency-jazz-thursday"

    occ3 = expanded[2]
    assert occ3["date"] == "2026-10-22"
    assert occ3["id"] == "residency-jazz-thursday_occ_2026-10-22"
    assert occ3["startsAt"] == "2026-10-22T20:00:00-07:00"
    assert occ3["endsAt"] == "2026-10-22T23:00:00-07:00"
    assert occ3["isRecurring"] is True


def test_filter_archived_events():
    events = [
        {
            "id": "e_yesterday",
            "startsAt": "2026-10-08T20:00:00-07:00",
            "endsAt": "2026-10-08T23:00:00-07:00",
        },
        {
            "id": "e_now",
            "startsAt": "2026-10-09T20:00:00-07:00",
            "endsAt": "2026-10-09T23:00:00-07:00",
        },
        {
            "id": "e_tomorrow",
            "startsAt": "2026-10-10T20:00:00-07:00",
            "endsAt": "2026-10-10T23:00:00-07:00",
        },
    ]

    freeze_now = datetime(2026, 10, 9, 21, 0, 0, tzinfo=LA)
    active, archived = filter_archived_events(events, as_of=freeze_now)

    assert len(archived) == 1
    assert archived[0]["id"] == "e_yesterday"

    assert len(active) == 2
    active_ids = {e["id"] for e in active}
    assert "e_now" in active_ids
    assert "e_tomorrow" in active_ids
