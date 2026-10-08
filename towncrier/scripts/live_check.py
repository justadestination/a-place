#!/usr/bin/env python3
"""Live end-to-end check: discover branches, then enrich one.

Not part of the test suite. This is the run that answers the question the
unit tests cannot: does the tree actually fill up from live sources, and is
the coverage honest about its own gaps?

Usage:  python3 scripts/live_check.py [--enrich N]
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from towncrier import discover, facts
from towncrier.entities import ITEM_KINDS, KIND_SOCIAL, KIND_WEBSITE, ensure_entity, item_confidence
from towncrier.entities import add_item, uncited, venue_dossier

# Sebastopol + Metropolis, generously boxed.
BBOX = (38.28, -122.85, 38.52, -122.55)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--enrich", type=int, default=5,
                    help="how many discovered venues to crawl")
    ap.add_argument("--db", default=None)
    args = ap.parse_args()

    tmp = None
    if args.db:
        db_path = Path(args.db)
    else:
        tmp = tempfile.TemporaryDirectory()
        db_path = Path(tmp.name) / "live.db"

    from towncrier.store import Store
    store = Store(db_path)

    # ---- the trunk
    city_id = ensure_entity(store, name="Metropolis", kind="city",
                            meta={"note": "trunk; Sebastopol included"})

    print(f"db: {db_path}\n")

    # ---- discovery
    client = discover.OverpassClient()
    print(f"discovering venues in {BBOX} ...")
    candidates, failures = client.discover_area(BBOX, sleep_between_tiles=0.6)

    print(f"\n  {len(candidates)} candidates")
    music = [c for c in candidates if c.is_music_venue]
    print(f"  {len(music)} classified as music branches")
    if failures:
        print(f"\n  !! {len(failures)} tiles FAILED (coverage is incomplete):")
        for f in failures[:5]:
            print(f"     {f}")

    print("\n  top branches by confidence:")
    for c in music[:15]:
        print(f"    {c.score:>2}  {c.name[:34]:<34} {c.tags.get('amenity','-'):<14} {c.reasons[0] if c.reasons else ''}")

    # ---- write branches onto the trunk
    written = 0
    for c in music:
        vid = ensure_entity(store, name=c.name, kind="venue", parent_id=city_id,
                            role="host",
                            meta={"osm_type": c.osm_type, "osm_id": c.osm_id,
                                  "lat": c.lat, "lon": c.lon, "score": c.score,
                                  "reasons": c.reasons})
        add_item(store, entity_id=vid, kind=KIND_SOCIAL,
                 value=f"osm:{c.osm_type}/{c.osm_id}",
                 display=c.name,
                 source_id=f"osm:{c.osm_type}/{c.osm_id}",
                 source_url=c.osm_url, citation_kind="html",
                 excerpt="; ".join(c.reasons) or None)
        written += 1
    print(f"\n  {written} branches written onto the trunk")

    # ---- enrichment: crawl the sites we found
    print(f"\nenriching up to {args.enrich} branches from their own sites...")
    have_site = []
    for c in music:
        site = c.tags.get("website") or c.tags.get("contact:website") or c.tags.get("url")
        if site:
            if not site.startswith("http"):
                site = "http://" + site
            have_site.append((c, site))

    print(f"  {len(have_site)} branches have a website in OSM to crawl")

    enriched = 0
    for c, site in have_site[: args.enrich]:
        vid = ensure_entity(store, name=c.name, kind="venue", parent_id=city_id, role="host")
        res = facts.enrich_venue(store, vid, site)
        got = res.get("by_method", {})
        status = "ok" if res["written"] else ("FAILED" if res.get("error") else "no facts")
        print(f"    {c.name[:26]:<26} {str(res['http_status']):>4}  "
              f"{res['written']:>2} facts  {status}"
              + (f"  {got}" if got else ""))
        if res.get("error"):
            print(f"        {res['error']}")
        if res["written"]:
            enriched += 1

    print(f"\n  {enriched}/{min(args.enrich, len(have_site))} crawls produced facts")

    # ---- the guarantee
    uncited_rows = uncited(store)
    print(f"\nuncited facts: {len(uncited_rows)}  <-- must be 0")
    if uncited_rows:
        for r in uncited_rows[:5]:
            print(f"    {r['kind']} {r['value']!r}")

    # ---- coverage honesty
    print("\ncoverage of discovered branches:")
    for kind in ITEM_KINDS:
        n = store.one(
            f"SELECT COUNT(*) c FROM items WHERE kind=?", (kind,))["c"]
        print(f"    {kind:<10} {n:>4}")

    print("\nsample dossier:")
    for c, site in have_site[:2]:
        vid = ensure_entity(store, name=c.name, kind="venue", parent_id=city_id, role="host")
        dos = venue_dossier(store, vid)
        print(f"\n  {dos['name']}")
        for kind, vals in sorted(dos["facts"].items()):
            for v in vals[:2]:
                flag = " DISPUTED" if v["disputed"] else ""
                print(f"    {kind:<10} {str(v['value'])[:46]:<46} "
                      f"conf={v['confidence']}{flag}")
                for s in v["sources"][:1]:
                    print(f"               <- {s['url'][:80]} ({s['kind']})")
        if dos["not_found"]:
            print(f"    not found: {', '.join(dos['not_found'])}")

    store.close()
    if tmp:
        tmp.cleanup()
    return 0 if not uncited_rows else 1


if __name__ == "__main__":
    sys.exit(main())