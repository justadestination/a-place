"""RFC 5545 compliance and iCal feed tests (Task 5.5)."""

import pytest
from shadenet.nightcal import ical


def test_empty_feed():
    body = ical.build_ical(None, [])
    assert body.startswith("BEGIN:VCALENDAR")
    assert body.rstrip().endswith("END:VCALENDAR")
    assert "CALSCALE:GREGORIAN" in body
    assert "X-WR-CALNAME:" in body
    assert "X-WR-CALDESC:" in body
    assert "X-WR-TIMEZONE:America/Los_Angeles" in body


def test_rfc5545_compliance_and_events():
    events = [
        {
            "id": "evt_0000000000000001",
            "title": "Main Street Tavern Weekday Food Trucks",
            "starts_at": "2026-10-02T18:00:00+00:00",
            "ends_at": "2026-10-02T21:00:00+00:00",
            "status": "EventScheduled",
            "venue": "Main Street Tavern",
            "venueId": "ven_47b8847d9089d868",
        },
        {
            "id": "evt_0000000000000002",
            "title": "A Cancelled Show",
            "starts_at": "2026-10-05T20:00:00-07:00",
            "ends_at": "2026-10-05T23:00:00-07:00",
            "status": "EventCancelled",
            "venue": "The Velvet Tap",
            "venueId": "ven_2c9e0810fb65ed37",
            "address": "614 4th Street, Santa Rosa",
        },
    ]

    body = ical.build_ical(None, events)

    # Basic RFC 5545 calendar markers
    assert body.startswith("BEGIN:VCALENDAR\r\n") or body.startswith("BEGIN:VCALENDAR\n")
    assert "VERSION:2.0" in body
    assert "CALSCALE:GREGORIAN" in body
    assert "METHOD:PUBLISH" in body
    assert "X-WR-CALNAME:" in body
    assert "X-WR-CALDESC:" in body
    assert "X-WR-TIMEZONE:America/Los_Angeles" in body
    assert "DTSTAMP:" in body
    assert body.rstrip().endswith("END:VCALENDAR")

    # Event 1 checks
    assert "evt_0000000000000001@shady.example.org" in body
    assert "DTSTART;TZID=America/Los_Angeles:" in body
    assert "DTEND;TZID=America/Los_Angeles:" in body
    assert "STATUS:CONFIRMED" in body
    assert "SUMMARY:Main Street Tavern Weekday Food Trucks" in body

    # Event 2 checks (cancelled show must be cancelled, not dropped)
    assert "evt_0000000000000002@shady.example.org" in body
    assert "STATUS:CANCELLED" in body
    assert "The Velvet Tap, 614 4th Street, Santa Rosa" in body


def test_line_folding_rfc5545():
    long_event = [
        {
            "id": "evt_long_description",
            "title": "A Very Long Concert Title That Will Exercise The RFC 5545 Line Folding Logic Thoroughly",
            "starts_at": "2026-10-15T19:00:00+00:00",
            "ends_at": "2026-10-15T23:00:00+00:00",
            "venue": "Epic Downtown Venue With A Long Name Located At A Long Address In Santa Rosa California",
        }
    ]
    body = ical.build_ical(None, long_event)
    for line in body.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75, f"Line exceeds 75 octets: {line}"


def test_feed_etags_and_caching():
    events = [
        {
            "id": "evt_test_etag",
            "title": "Etag Test Event",
            "starts_at": "2026-10-10T20:00:00+00:00",
        }
    ]
    headers = ical.feed_etags(events)
    assert "ETag" in headers
    assert headers["ETag"].startswith('"') and headers["ETag"].endswith('"')
    assert "Last-Modified" in headers
    assert "GMT" in headers["Last-Modified"]
