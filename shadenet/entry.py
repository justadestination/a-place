# Shadenet — dynamic geographic bootstrap entry point (TASK-02)
#
# Container-first entry point for the autonomous single-container packaging.
# When SHADENET_LAT / SHADENET_LON / SHADENET_RADIUS_KM are set, the entry
# point computes the bounding box, queries OSM Overpass, and populates SQLite
# automatically on first boot. When unset (local dev), it falls back to the
# existing nightcal.fill / horizon.zine_pipeline behaviour.
#
# Dispatch (from Dockerfile ENTRYPOINT):
#   shadenet   - first-boot bootstrap (discover venues + populate DB), then serve
#   fill       - just populate the DB from existing sources
#   server     - pure web server, no discovery (DB already seeded)
#   zine       - compile the zine AVR node-graph
#
# Usage as a module (docker-entrypoint.py):
#   python3 -m shadenet.entry
#
# Environment of record (shell-escaped, never committed):
#   SHADENET_LAT        centre latitude (e.g. 37.7749 for Metropolis)
#   SHADENET_LON        centre longitude
#   SHADENET_RADIUS_KM  discovery radius in kilometres (e.g. 25)
#   SHADENET_DB         optional absolute path to SQLite (default data/shadenet.db)
#   NIGHTCAL_PORT       web server port (default 8765)
#   NIGHTCAL_HOST       bind address (default 127.0.0.1)
#   SHADENET_DEV_MODE   enable ZKP 21+ dev bypass (default off)

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shadenet.nightcal import fill as nightcal_fill  # noqa: E402
import shadenet.horizon.zine_pipeline as zine_pipeline  # noqa: E402
from shadenet.towncrier.store import Store  # noqa: E402
from shadenet.towncrier import discover as towncrier_discover  # noqa: E402


# ---------------------------------------------------------------------------
# Geographic bootstrap
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _lon_bbox(lon: float, radius_km: float) -> tuple[float, float]:
    """Approx lon span for a given radius (varies with latitude)."""
    circ = 40075.0 * math.cos(math.radians(lon))  # km per full longitude at this lat
    return (-radius_km / circ * 360.0, radius_km / circ * 360.0)


def compute_bounding_box(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    """(south, west, north, east) computed from centre + radius."""
    lat_step = radius_km / 111.0
    south = lat - lat_step
    north = lat + lat_step
    dlon = _lon_bbox(lon, radius_km)
    west = lon + dlon[0]
    east = lon + dlon[1]
    return (south, west, north, east)


def discover_and_fill(db_path: Path, lat: float, lon: float, radius_km: float) -> dict:
    """Run Overpass grid discovery + the fill pass, populate the database."""
    from shadenet.towncrier.entities import (
        KIND_ADDRESS,
        KIND_EMAIL,
        KIND_PHONE,
        KIND_SOCIAL,
        KIND_WEBSITE,
        add_item,
        ensure_entity,
    )

    bbox = compute_bounding_box(lat, lon, radius_km)
    print(f"[shadenet] bbox (S,W,N,E) = {bbox}", flush=True)

    # Reuse the existing tile-based grid discovery from towncrier.discover.
    client = towncrier_discover.OverpassClient(
        cache_dir=ROOT / ".cache" / "overpass",
        endpoints=(
            "https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.osm.jp/api/interpreter",
        ),
        min_interval_sec=0.5,
        timeout_sec=60,
        max_retries=2,
    )
    candidates, failures = client.discover_area(
        bbox,
        selectors=towncrier_discover.VENUE_SELECTORS,
        max_deg=0.06,
        require_name=True,
        sleep_between_tiles=1.0,
    )
    print(f"[shadenet] candidates = {len(candidates)}, tile failures = {len(failures)}", flush=True)
    if failures:
        print(f"[shadenet] failed tiles: {failures[:5]}", flush=True)

    # Populate venues into SQLite via the existing fill logic.
    store = Store(db_path)
    try:
        city = ensure_entity(store, name="Metropolis", kind="city", role="host",
                             meta={"downtown_bbox": list(bbox), "discovered": True})
        written = 0
        for c in candidates:
            meta = {
                "osm_type": c.osm_type,
                "osm_id": c.osm_id,
                "lat": c.lat,
                "lon": c.lon,
                "score": c.score,
                "reasons": c.reasons,
                "amenity": c.tags.get("amenity", ""),
                "music": c.is_music_venue,
                "downtown": True,
            }
            ent = ensure_entity(store, name=c.name, kind="venue", parent_id=city,
                                role="host", meta=meta)
            store.execute("UPDATE entities SET meta = ? WHERE id = ?",
                          (json.dumps(meta), ent))
            store.ensure_venue(
                c.name,
                address="",
                city="Metropolis",
                state="CA",
                lat=c.lat,
                lon=c.lon,
                website=c.tags.get("website") or c.tags.get("contact:website"),
            )
            source = f"osm:{c.osm_type}/{c.osm_id}"
            osm_url = c.osm_url
            add_item(store, entity_id=ent, kind=KIND_SOCIAL,
                     value=f"osm:{c.osm_type}/{c.osm_id}", display=c.name,
                     source_id=source, source_url=osm_url,
                     citation_kind="html", excerpt=c.tags.get("amenity") or "venue")
            address = f"{c.tags.get('addr:housenumber','')} {c.tags.get('addr:street','')}".strip()
            if address:
                add_item(store, entity_id=ent, kind=KIND_ADDRESS, value=address,
                         source_id=source, source_url=osm_url, citation_kind="html")
            phone = c.tags.get("phone") or c.tags.get("contact:phone")
            if phone:
                add_item(store, entity_id=ent, kind=KIND_PHONE, value=phone,
                         display=phone, source_id=source, source_url=osm_url,
                         citation_kind="html")
            website = c.tags.get("website") or c.tags.get("contact:website") or c.tags.get("url")
            if website:
                add_item(store, entity_id=ent, kind=KIND_WEBSITE, value=website,
                         source_id=source, source_url=osm_url, citation_kind="html")
            written += 1
        print(f"[shadenet] venues written = {written}", flush=True)
    finally:
        store.close()

    # Full fill pass (contacts, social, calendar sync) via the existing module.
    return nightcal_fill(db_path=db_path)


def first_boot(db_path: Path) -> bool:
    """True if the DB has no venues yet → run the autonomous bootstrap."""
    if not db_path.exists():
        return True
    store = Store(db_path)
    try:
        n = store.query("SELECT COUNT(*) AS n FROM venues")[0]["n"]
        return n == 0
    finally:
        store.close()


def main() -> int:
    import math

    lat = os.environ.get("SHADENET_LAT")
    lon = os.environ.get("SHADENET_LON")
    radius = os.environ.get("SHADENET_RADIUS_KM")
    db_env = os.environ.get("SHADENET_DB")
    db_path = Path(db_env) if db_env else (ROOT / "data" / "shadenet.db")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    if lat and lon and radius:
        try:
            lat_f = float(lat)
            lon_f = float(lon)
            radius_f = float(radius)
        except ValueError:
            print("[shadenet] SHADENET_LAT/LON/RADIUS_KM are not valid floats; "
                  "falling back to the existing fill.", flush=True)
        else:
            if first_boot(db_path):
                print(f"[shadenet] first boot: running autonomous geographic bootstrap "
                      f"for {lat_f}, {lon_f} radius {radius_f} km", flush=True)
                summary = discover_and_fill(db_path, lat_f, lon_f, radius_f)
                print(f"[shadenet] bootstrap summary = {json.dumps(summary)}", flush=True)

    # Hand off to the existing night calendar + zine pipeline (subprocess so the
    # correct interpreter and package prefix is used).
    args = [sys.executable, "-m", "shadenet.nightcal.fill"]
    if os.environ.get("SHADENET_DEV_MODE"):
        args.append("--dev-mode")
    subprocess.run(args, check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
