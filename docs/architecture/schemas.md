# Architecture Specification: Versioned Schemas for Venues & Cultural Entities

## 1. Principles & Overview

NightCal models the civic and cultural ecosystem of Downtown Santa Rosa and expanding regions through structured, versioned schemas. Every venue, promoter, band, and comedian conforms to strict validation rules enforced at write time, with automated migration hooks for version upgrades.

### Core Principles
1. **Explicit Identification**: Every entity has a permanent, globally unique identifier (`id`).
2. **Versioned Documents**: Every payload specifies `schema_version` (currently `v2`).
3. **Status Lifecycle**: Entities are never blindly deleted; their lifecycle state reflects physical reality (`active`, `closed`, `renovating`, `hiatus`).
4. **Resilient Migration**: Upgrades are non-destructive, with automated transformation pipelines (`migrate_entity`).

---

## 2. Entity Schema Specifications (v2)

### 2.1 Venue Schema
```json
{
  "id": "ven_a261886187f23bb1",
  "name": "Echo Music Hall",
  "status": "active",
  "address": "120 5th Street, Santa Rosa, CA",
  "lat": 38.4383393,
  "lon": -122.7199914,
  "timezone": "America/Los_Angeles",
  "amenity": "music_venue",
  "music": true,
  "contact": {
    "phones": [{ "text": "+1-707-542-1455", "href": "tel:+17075421455" }],
    "emails": [{ "text": "booking@echohall.org", "href": "mailto:booking@echohall.org" }],
    "websites": ["https://echohall.org"],
    "socials": []
  },
  "schema_version": "v2"
}
```

#### Status Lifecycle
- `active`: Regularly scheduled events; listed in all views.
- `closed`: Permanently closed; filtered from calendar listings.
- `renovating`: Temporarily offline; listed with an informational notice.
- `temporarily_closed`: Off-season or seasonal hiatus.

---

### 2.2 Promoter Schema
```json
{
  "id": "prom_north_bay_indie",
  "type": "promoter",
  "name": "North Bay Indie Collective",
  "status": "active",
  "bio": "Curating DIY and underground indie showcases across Sonoma County.",
  "venues": ["ven_a261886187f23bb1"],
  "contact": {
    "emails": [{ "text": "hello@northbayindie.org", "href": "mailto:hello@northbayindie.org" }]
  },
  "schema_version": "v2"
}
```

---

### 2.3 Band / Artist Schema
```json
{
  "id": "band_paradise_inferno",
  "type": "band",
  "name": "Paradise Inferno",
  "status": "active",
  "genre": "Psych Surf Rock",
  "members": ["Elena Vance", "Marcus Cruz", "Dave Kim"],
  "bio": "High-octane fuzz guitars from the Sonoma coast.",
  "schema_version": "v2"
}
```

---

### 2.4 Comedian Schema
```json
{
  "id": "com_downtown_chuckle",
  "type": "comedian",
  "name": "Maya Lin",
  "status": "active",
  "style": "Observational / Deadpan",
  "bio": "Resident comic at Santa Rosa Friday open-mic sessions.",
  "schema_version": "v2"
}
```

---

## 3. Schema Migration Pipeline (v1 $\to$ v2)

When an incoming payload or stored legacy record has `schema_version = "v1"`, the migration pipeline applies automated transformations:
1. **Status Canonicalization**: Legacy `closed: true` boolean is converted to `status: "closed"`.
2. **Timezone Annotation**: Adds default `timezone: "America/Los_Angeles"` if omitted.
3. **Contact Structuring**: Flat `phone` and `email` string attributes are converted to structured list arrays (`phones: [...]`, `emails: [...]`).
