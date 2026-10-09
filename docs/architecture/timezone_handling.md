# Architecture Specification: Timezone Correctness & Multi-Region Event Handling

## 1. Overview & Principles

NightCal is a hyperlocal live event guide originating in Downtown Santa Rosa (`America/Los_Angeles`). As the network expands across regions, event scheduling must guarantee strict temporal accuracy across diverse venues, borders, and Daylight Saving Time (DST) changes.

### Core Tenets
1. **Explicit Storage**: All events are stored with ISO-8601 timestamps with explicit UTC offsets (`YYYY-MM-DDTHH:MM:SS-07:00`) or normalized UTC (`YYYY-MM-DDTHH:MM:SSZ`).
2. **Venue-Local Rendering**: Event times are rendered in the **venue's local timezone**, never arbitrarily converted to the viewer's arbitrary browser timezone. If a concert starts at 8:00 PM in Brooklyn, a user viewing the schedule from California must see `8:00 pm EDT`, not 5:00 PM.
3. **Transparent Abbreviation**: Time strings include the localized standard timezone abbreviation (e.g. `8:00 pm PDT`, `8:00 pm EDT`) to eliminate confusion for traveling patrons and cross-region performers.

---

## 2. Data Model & Schema Extensions

### 2.1 Venue Schema
Venues define their operational timezone in IANA format:
```json
{
  "id": "v_brooklyn_bowl",
  "name": "Brooklyn Bowl",
  "address": "61 Wythe Ave, Brooklyn, NY 11249",
  "timezone": "America/New_York"
}
```
*Note: If omitted, `timezone` defaults to `America/Los_Angeles`.*

### 2.2 Event Schema
```json
{
  "id": "ev_jazz_night",
  "venueId": "v_brooklyn_bowl",
  "date": "2026-10-08",
  "startsAt": "2026-10-08T20:00:00-04:00",
  "endsAt": "2026-10-08T23:00:00-04:00",
  "timezone": "America/New_York",
  "tzAbbr": "EDT",
  "localizedStart": "8:00 pm EDT",
  "timeDisplay": "8:00 pm – 11:00 pm EDT"
}
```

---

## 3. Daylight Saving Time (DST) Handling

Python `zoneinfo.ZoneInfo` and browser `Intl.DateTimeFormat` implement the standard IANA timezone database.

### 3.1 Spring Forward Transition (Gap)
- In the US, clocks advance from `01:59:59` to `03:00:00` on the second Sunday of March.
- Wall-clock time skips 02:00:00–02:59:59.
- Offset transitions from `-08:00` (PST) to `-07:00` (PDT).
- Real elapsed time across the transition is computed via normalized UTC instances:
  $$\Delta t = t_{\text{after, UTC}} - t_{\text{before, UTC}}$$

### 3.2 Fall Back Transition (Fold)
- On the first Sunday of November, clocks fall back from `01:59:59` to `01:00:00`.
- The hour between 01:00 and 02:00 occurs twice (first with fold 0 in PDT, then with fold 1 in PST).
- Offset transitions from `-07:00` (PDT) to `-08:00` (PST).

---

## 4. Verification & Testing Strategy
- Unit tests (`tests/test_timezone.py`): verify exact UTC conversion, multi-timezone formatting, and millisecond-level elapsed time accuracy across DST gaps and folds.
- End-to-end tests (`web/tests/test_timezone.mjs`): verify seeded events from multiple timezones render correctly with distinct abbreviations and pass full WCAG 2.2 AA accessibility audits.
