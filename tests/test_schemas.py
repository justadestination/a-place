"""
Unit tests for venue and entity schemas & migration engine (Task 2.11).
"""

import pytest
from shadenet.nightcal.schemas import (
    validate_venue,
    validate_promoter,
    validate_band,
    validate_comedian,
    validate_entity,
    migrate_entity,
    SchemaValidationError,
    CURRENT_SCHEMA_VERSION,
)


def test_validate_venue_valid():
    payload = {
        "id": "ven_ar_theater",
        "name": "California Theater",
        "address": "528 7th St, Santa Rosa, CA",
        "lat": 38.441,
        "lon": -122.714,
        "status": "active",
        "timezone": "America/Los_Angeles",
        "music": True,
        "contact": {"phones": [], "emails": []},
    }
    validated = validate_venue(payload)
    assert validated["id"] == "ven_ar_theater"
    assert validated["name"] == "California Theater"
    assert validated["status"] == "active"
    assert validated["closed"] is False
    assert validated["schema_version"] == CURRENT_SCHEMA_VERSION


def test_validate_venue_closed_and_renovating():
    payload_closed = {
        "id": "ven_old_pub",
        "name": "The Old Shutter Pub",
        "status": "closed",
    }
    v_closed = validate_venue(payload_closed)
    assert v_closed["closed"] is True
    assert v_closed["status"] == "closed"

    payload_reno = {
        "id": "ven_reno",
        "name": "Downtown Stage",
        "status": "renovating",
    }
    v_reno = validate_venue(payload_reno)
    assert v_reno["status"] == "renovating"


def test_validate_venue_rejections():
    # Missing ID
    with pytest.raises(SchemaValidationError) as exc:
        validate_venue({"name": "No ID Club"})
    assert "Venue 'id' is required" in str(exc.value)

    # Missing Name
    with pytest.raises(SchemaValidationError) as exc:
        validate_venue({"id": "ven_no_name"})
    assert "Venue 'name' is required" in str(exc.value)

    # Invalid status
    with pytest.raises(SchemaValidationError) as exc:
        validate_venue({"id": "v1", "name": "Test", "status": "demolished"})
    assert "Invalid venue status" in str(exc.value)

    # Out of range coordinates
    with pytest.raises(SchemaValidationError) as exc:
        validate_venue({"id": "v1", "name": "Test", "lat": 150.0})
    assert "Latitude must be between -90 and +90" in str(exc.value)


def test_entity_validators_promoter_band_comedian():
    # Promoter
    promoter = validate_promoter({"id": "prom_1", "name": "North Bay Bookings", "status": "active"})
    assert promoter["type"] == "promoter"
    assert promoter["status"] == "active"

    # Band
    band = validate_band({"id": "band_1", "name": "The Velvet Midnight", "status": "hiatus", "genre": "Indie Rock"})
    assert band["type"] == "band"
    assert band["status"] == "hiatus"

    # Comedian
    comic = validate_comedian({"id": "com_1", "name": "Sarah Silverman Tribute", "status": "active"})
    assert comic["type"] == "comedian"

    # Router
    routed = validate_entity("venue", {"id": "v_routed", "name": "Routed Venue"})
    assert routed["id"] == "v_routed"


def test_schema_migration_v1_to_v2():
    """Verify legacy v1 documents migrate seamlessly to v2 specifications."""
    v1_legacy_venue = {
        "id": "ven_legacy_101",
        "name": "Historic Redwood Saloon",
        "closed": True,
        "phone": "+1-707-555-0199",
        "email": "info@redwoodsaloon.org",
        "schema_version": "v1",
    }

    v2_migrated = migrate_entity(v1_legacy_venue, target_version="v2")
    assert v2_migrated["schema_version"] == "v2"
    assert v2_migrated["status"] == "closed"
    assert v2_migrated["timezone"] == "America/Los_Angeles"
    assert "phones" in v2_migrated["contact"]
    assert v2_migrated["contact"]["phones"][0]["text"] == "+1-707-555-0199"
    assert v2_migrated["contact"]["emails"][0]["text"] == "info@redwoodsaloon.org"

    # Ensure migrated document passes v2 validator
    validated = validate_venue(v2_migrated)
    assert validated["closed"] is True
    assert validated["schema_version"] == "v2"
