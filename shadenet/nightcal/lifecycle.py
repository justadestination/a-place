"""Event lifecycle engine (Task 2.9).

Handles:
  1. "Happening now" state calculation (upcoming -> happening_now -> past/archived).
  2. Past events archive filtering.
  3. Recurring events expansion (weekly residencies, ISO recurrence rules) across multi-week horizons.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any

LA = ZoneInfo("America/Los_Angeles")
DEFAULT_DURATION_HOURS = 3.0


def parse_datetime(val: str | datetime | None, default_tz: ZoneInfo = LA) -> datetime | None:
    if not val:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=default_tz)
        return val
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=default_tz)
        return dt
    except Exception:
        # Check YYYY-MM-DD
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", val.strip())
        if m:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return datetime(d.year, d.month, d.day, 20, 0, tzinfo=default_tz)
        return None


def compute_event_lifecycle(
    starts_at: str | datetime | None,
    ends_at: str | datetime | None = None,
    now: datetime | None = None,
    default_duration_hours: float = DEFAULT_DURATION_HOURS,
) -> dict[str, Any]:
    """Compute event lifecycle: 'upcoming', 'happening_now', or 'past' (archived)."""
    current_now = now or datetime.now(timezone.utc)
    if current_now.tzinfo is None:
        current_now = current_now.replace(tzinfo=timezone.utc)

    start_dt = parse_datetime(starts_at)
    if not start_dt:
        return {
            "state": "upcoming",
            "happening_now": False,
            "is_past": False,
            "is_archived": False,
            "starts_at": "",
            "ends_at": "",
        }

    # Normalize current_now to the same timezone as start_dt
    tz = start_dt.tzinfo or LA
    now_tz = current_now.astimezone(tz)

    end_dt = parse_datetime(ends_at, default_tz=tz)
    if not end_dt:
        end_dt = start_dt + timedelta(hours=default_duration_hours)
    else:
        end_dt = end_dt.astimezone(tz)

    if now_tz < start_dt:
        state = "upcoming"
        happening_now = False
        is_past = False
    elif start_dt <= now_tz <= end_dt:
        state = "happening_now"
        happening_now = True
        is_past = False
    else:
        state = "past"
        happening_now = False
        is_past = True

    return {
        "state": state,
        "happening_now": happening_now,
        "is_past": is_past,
        "is_archived": is_past,
        "starts_at": start_dt.isoformat(),
        "ends_at": end_dt.isoformat(),
    }


def expand_recurring_events(
    events: list[dict[str, Any]],
    start_date: date | str,
    end_date: date | str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Expands recurring events (weekly residencies) across the given date range.

    If an event has recurrence (e.g. recurrence="weekly", recurrence={"freq": "weekly"}),
    occurrences are generated for every 7 days through end_date.
    """
    s_date = date.fromisoformat(start_date) if isinstance(start_date, str) else start_date
    e_date = date.fromisoformat(end_date) if isinstance(end_date, str) else end_date

    expanded: list[dict[str, Any]] = []

    for ev in events:
        recurrence = ev.get("recurrence")
        is_rec = bool(ev.get("isRecurring") or ev.get("is_recurring") or recurrence)

        if not is_rec:
            # Non-recurring event: keep if within or after range
            ev_date_str = ev.get("date")
            if ev_date_str:
                try:
                    ev_date = date.fromisoformat(ev_date_str)
                    if s_date <= ev_date <= e_date:
                        expanded.append(ev)
                except ValueError:
                    expanded.append(ev)
            else:
                expanded.append(ev)
            continue

        # Recurring event expansion
        base_date_str = ev.get("date")
        if not base_date_str:
            expanded.append(ev)
            continue

        try:
            base_date = date.fromisoformat(base_date_str)
        except ValueError:
            expanded.append(ev)
            continue

        base_start = parse_datetime(ev.get("startsAt") or ev.get("starts_at"))
        base_end = parse_datetime(ev.get("endsAt") or ev.get("ends_at"))

        # Advance or rewind base_date to find occurrences in [s_date, e_date]
        # Weekly recurrence: same day of week (step 7 days)
        # Find first occurrence >= s_date with same weekday as base_date
        days_ahead = (base_date.weekday() - s_date.weekday()) % 7
        curr_occ = s_date + timedelta(days=days_ahead)
        if curr_occ < base_date:
            curr_occ = base_date

        occ_count = 0
        while curr_occ <= e_date:
            occ_count += 1
            days_delta = (curr_occ - base_date).days
            occ_start = (base_start + timedelta(days=days_delta)) if base_start else None
            occ_end = (base_end + timedelta(days=days_delta)) if base_end else None

            occ_date_str = curr_occ.isoformat()
            is_base = (curr_occ == base_date)
            occ_id = ev["id"] if is_base else f"{ev['id']}_occ_{occ_date_str}"

            occ_ev = dict(ev)
            occ_ev["id"] = occ_id
            occ_ev["date"] = occ_date_str
            occ_ev["isRecurring"] = True
            occ_ev["is_recurring"] = True
            occ_ev["baseEventId"] = ev["id"]
            occ_ev["occurrenceIndex"] = occ_count

            if occ_start:
                occ_ev["startsAt"] = occ_start.isoformat()
                occ_ev["starts_at"] = occ_start.isoformat()
            if occ_end:
                occ_ev["endsAt"] = occ_end.isoformat()
                occ_ev["ends_at"] = occ_end.isoformat()

            # Recompute lifecycle for this occurrence
            lc = compute_event_lifecycle(
                starts_at=occ_ev.get("startsAt"),
                ends_at=occ_ev.get("endsAt"),
                now=now,
            )
            occ_ev["lifecycle"] = lc["state"]
            occ_ev["happeningNow"] = lc["happening_now"]
            occ_ev["isPast"] = lc["is_past"]
            occ_ev["isArchived"] = lc["is_archived"]

            expanded.append(occ_ev)
            curr_occ += timedelta(days=7)

    return expanded


def filter_archived_events(
    events: list[dict[str, Any]],
    as_of: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split events into active/upcoming vs archived/past."""
    active = []
    archived = []
    for ev in events:
        lc = compute_event_lifecycle(
            starts_at=ev.get("startsAt") or ev.get("starts_at"),
            ends_at=ev.get("endsAt") or ev.get("ends_at"),
            now=as_of,
        )
        if lc["is_past"]:
            archived.append(ev)
        else:
            active.append(ev)
    return active, archived
