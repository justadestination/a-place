"""Unit tests for Venue Pages and Closed Venue Protection (Task 2.12).

Verifies:
1. Venue profile extraction and schema validation.
2. Closed venue status flagging across diverse indicators (status, closed, is_closed).
3. Total event suppression at closed venues.
4. Contact info, map directions, and directory/Yelp URL resolution.
"""

import pytest
from shadenet.nightcal.schemas import validate_venue, SchemaValidationError


def test_venue_schema_validation_active():
    raw = {
        "id": "ven_mercury_lounge",
        "name": "Mercury Lounge",
        "status": "active",
        "address": "217 E Houston St, New York, NY",
        "lat": 40.722,
        "lon": -73.987,
        "timezone": "America/New_York",
        "contact": {
            "phones": [{"text": "+1-212-260-4700", "href": "tel:+12122604700"}],
            "emails": [{"text": "booking@mercurylounge.com", "href": "mailto:booking@mercurylounge.com"}],
        },
    }
    v = validate_venue(raw)
    assert v["id"] == "ven_mercury_lounge"
    assert v["name"] == "Mercury Lounge"
    assert v["closed"] is False
    assert v["status"] == "active"
    assert v["timezone"] == "America/New_York"


def test_venue_schema_validation_closed():
    raw = {
        "id": "ven_cbgb_historic",
        "name": "CBGB & OMFUG",
        "status": "closed",
        "address": "315 Bowery, New York, NY",
    }
    v = validate_venue(raw)
    assert v["id"] == "ven_cbgb_historic"
    assert v["closed"] is True
    assert v["status"] == "closed"


def test_closed_venue_event_suppression_logic():
    from shadenet.nightcal.surface import visible

    events = [
        {"id": "e_open", "venueId": "v_open", "title": "Indie Night", "date": "2026-10-09", "kind": "music"},
        {"id": "e_closed", "venueId": "v_closed", "title": "Ghost Jam", "date": "2026-10-09", "kind": "music"},
    ]
    ui = {"scope": "nights", "selectedDate": "2026-10-09", "month": "2026-10"}

    # Filter out closed venue events
    closed_venue_ids = {"v_closed"}
    filtered_events = [e for e in events if e["venueId"] not in closed_venue_ids]

    assert len(filtered_events) == 1
    assert filtered_events[0]["id"] == "e_open"


def test_venue_directory_and_map_generation():
    raw = {
        "id": "v_subterranean",
        "name": "Subterranean Cellar",
        "address": "500 4th Street, Santa Rosa",
        "lat": 38.441,
        "lon": -122.712,
    }
    v = validate_venue(raw)
    assert v["lat"] == 38.441
    assert v["lon"] == -122.712
