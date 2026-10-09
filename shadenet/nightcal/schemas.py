"""
shadenet.nightcal.schemas — Documented, versioned schemas for venues and entities (Task 2.11).

Defines:
  1. Schemas for venues, promoters, bands, and comedians.
  2. Required vs optional fields, validation rules, and status lifecycles.
  3. Schema migration engine for version bumps (v1 -> v2).
"""

from __future__ import annotations

import re
from typing import Any, Literal
from dataclasses import dataclass, field

CURRENT_SCHEMA_VERSION = "v2"

VENUE_STATUSES = {"active", "closed", "renovating", "temporarily_closed"}
ENTITY_STATUSES = {"active", "hiatus", "inactive", "split"}
ENTITY_TYPES = {"venue", "promoter", "band", "comedian"}


class SchemaValidationError(ValueError):
    """Raised when an entity payload fails schema validation."""
    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or [message]


def validate_venue(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a venue payload against schema."""
    if not isinstance(data, dict):
        raise SchemaValidationError("Venue payload must be a dictionary")

    errors: list[str] = []

    # Required fields
    vid = str(data.get("id") or "").strip()
    if not vid:
        errors.append("Venue 'id' is required")

    name = str(data.get("name") or "").strip()
    if not name:
        errors.append("Venue 'name' is required")

    status = str(data.get("status") or "active").strip().lower()
    if status not in VENUE_STATUSES:
        errors.append(f"Invalid venue status '{status}'. Must be one of {sorted(VENUE_STATUSES)}")

    # Coordinates validation
    lat = data.get("lat")
    lon = data.get("lon")
    if lat is not None:
        try:
            lat_f = float(lat)
            if not (-90.0 <= lat_f <= 90.0):
                errors.append(f"Latitude must be between -90 and +90, got {lat_f}")
        except (ValueError, TypeError):
            errors.append(f"Invalid latitude value: {lat}")

    if lon is not None:
        try:
            lon_f = float(lon)
            if not (-180.0 <= lon_f <= 180.0):
                errors.append(f"Longitude must be between -180 and +180, got {lon_f}")
        except (ValueError, TypeError):
            errors.append(f"Invalid longitude value: {lon}")

    # Timezone validation
    tz = data.get("timezone")
    if tz is not None and not isinstance(tz, str):
        errors.append("Venue 'timezone' must be a string")

    # Contact validation
    contact = data.get("contact", {})
    if not isinstance(contact, dict):
        errors.append("Venue 'contact' must be a dictionary")

    if errors:
        raise SchemaValidationError(f"Venue validation failed: {'; '.join(errors)}", errors)

    res = dict(data)
    res["id"] = vid
    res["name"] = name
    res["status"] = status
    res["schema_version"] = str(data.get("schema_version") or CURRENT_SCHEMA_VERSION)
    res["timezone"] = str(data.get("timezone") or "America/Los_Angeles")
    res["closed"] = status in ("closed", "temporarily_closed")
    return res


def validate_promoter(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a promoter entity payload."""
    errors: list[str] = []
    pid = str(data.get("id") or "").strip()
    if not pid:
        errors.append("Promoter 'id' is required")
    name = str(data.get("name") or "").strip()
    if not name:
        errors.append("Promoter 'name' is required")

    status = str(data.get("status") or "active").strip().lower()
    if status not in ENTITY_STATUSES:
        errors.append(f"Invalid promoter status '{status}'. Must be one of {sorted(ENTITY_STATUSES)}")

    if errors:
        raise SchemaValidationError(f"Promoter validation failed: {'; '.join(errors)}", errors)

    res = dict(data)
    res["type"] = "promoter"
    res["status"] = status
    res["schema_version"] = str(data.get("schema_version") or CURRENT_SCHEMA_VERSION)
    return res


def validate_band(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a band/musical group entity payload."""
    errors: list[str] = []
    bid = str(data.get("id") or "").strip()
    if not bid:
        errors.append("Band 'id' is required")
    name = str(data.get("name") or "").strip()
    if not name:
        errors.append("Band 'name' is required")

    status = str(data.get("status") or "active").strip().lower()
    if status not in ENTITY_STATUSES:
        errors.append(f"Invalid band status '{status}'. Must be one of {sorted(ENTITY_STATUSES)}")

    if errors:
        raise SchemaValidationError(f"Band validation failed: {'; '.join(errors)}", errors)

    res = dict(data)
    res["type"] = "band"
    res["status"] = status
    res["schema_version"] = str(data.get("schema_version") or CURRENT_SCHEMA_VERSION)
    return res


def validate_comedian(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a comedian entity payload."""
    errors: list[str] = []
    cid = str(data.get("id") or "").strip()
    if not cid:
        errors.append("Comedian 'id' is required")
    name = str(data.get("name") or "").strip()
    if not name:
        errors.append("Comedian 'name' is required")

    status = str(data.get("status") or "active").strip().lower()
    if status not in ENTITY_STATUSES:
        errors.append(f"Invalid comedian status '{status}'. Must be one of {sorted(ENTITY_STATUSES)}")

    if errors:
        raise SchemaValidationError(f"Comedian validation failed: {'; '.join(errors)}", errors)

    res = dict(data)
    res["type"] = "comedian"
    res["status"] = status
    res["schema_version"] = str(data.get("schema_version") or CURRENT_SCHEMA_VERSION)
    return res


def validate_entity(entity_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Generic validator router for any entity type."""
    t = entity_type.strip().lower()
    if t == "venue":
        return validate_venue(data)
    elif t == "promoter":
        return validate_promoter(data)
    elif t in ("band", "music_group", "artist"):
        return validate_band(data)
    elif t in ("comedian", "comic"):
        return validate_comedian(data)
    else:
        raise SchemaValidationError(f"Unknown entity type '{entity_type}'. Must be one of {sorted(ENTITY_TYPES)}")


def migrate_entity(data: dict[str, Any], target_version: str = CURRENT_SCHEMA_VERSION) -> dict[str, Any]:
    """Migrate legacy entity payloads (v1 -> v2).
    
    v1 -> v2 changes:
      - Ensures explicit 'timezone' on venues (defaults to 'America/Los_Angeles').
      - Normalizes 'closed' boolean into canonical 'status' string ('active' or 'closed').
      - Transforms flat contact fields (phone, email) into structured contact objects.
    """
    doc = dict(data)
    current_ver = str(doc.get("schema_version") or "v1")

    if current_ver == target_version:
        return doc

    # Migration: v1 -> v2
    if current_ver == "v1" and target_version == "v2":
        # Venue specific migration
        if "closed" in doc and "status" not in doc:
            doc["status"] = "closed" if doc["closed"] else "active"

        if "timezone" not in doc:
            doc["timezone"] = "America/Los_Angeles"

        # Migrate contact fields if flat
        contact = dict(doc.get("contact") or {})
        if "phone" in doc and "phones" not in contact:
            contact["phones"] = [{"text": doc["phone"], "href": f"tel:{doc['phone']}"}]
        if "email" in doc and "emails" not in contact:
            contact["emails"] = [{"text": doc["email"], "href": f"mailto:{doc['email']}"}]
        doc["contact"] = contact

        doc["schema_version"] = "v2"

    return doc
