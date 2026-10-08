"""Discovery: finding the branches without a seed list.

The first version of this project was going to be seeded by hand — someone
names a venue, we crawl it. That does not scale past a dozen rooms and, more
to the point, it means the *tree* is only as good as the seed list. This module
finds venues from a public gazetteer instead, so the trunk grows branches on
its own.

## Why OpenStreetMap rather than Google Maps

Both would find venues. Google Places was the obvious candidate and it is a
genuinely better gazetteer for commercial venues. It is also **forbidden** for
this project's core purpose, and not for cost reasons:

The Google Maps Platform Terms of Service restrict *caching and storage* of
Places content. You may display it and you may use place IDs, but you may not
persist it into your own database as a system of record. That is precisely what
we want to do — a durable venue dossier with phone, address and hours that
survives a crawl, is versioned, and is citable per fact. Storing Places data
like that is a ToS violation on day one. The API also has no "give me a
licensed dump" path at free tiers.

OpenStreetMap's ODbL licence says the opposite: store it, derive from it,
publish it, attribute it. That is the licence our project actually needs,
because our project *is* a database. So OSM is not the inferior fallback here
— it is the only one of the two whose terms permit the thing we are building.

There is a real cost, measured below and in `test_discover.py`: OSM's contact
tags are sparse. Roughly a quarter of Valley County venues carry a phone
number in OSM. So discovery from OSM gives us a *candidate list*, and the
second adapter (`facts.py`) is what actually fills the tree. Discovery and
enrichment are separate jobs, and conflating them is why a lot of scrapers end
up with thin records.

## Rationing

Overpass will return 504 on a heavy query and rate-limit aggressively. This
module: (1) splits large areas into a grid and sleeps between tiles, (2)
caches responses to disk keyed by query hash so a re-run costs no requests,
and (3) treats a tile failure as partial coverage, reported as such, rather
than silently returning a short list. A short list that looks complete is the
worst possible failure mode here — it would quietly under-populate the tree.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterator

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
)

USER_AGENT = "towncrier/0.1 (local event research; contact: operator)"

# OSM tags that mean "this place hosts live music". Deliberately inclusive:
# a brewery with a music room and a bingo hall are both branches, and it is
# cheaper to look at 40 candidates and drop 25 than to miss the 15 that matter.
#
# The `leisure=live_music_venue` / `music:type=*` tags are the precise ones,
# and in this area they are nearly empty (measured: zero `music:type` features
# in the Sebastopol+Metropolis bbox). The broad amenity tags do the real work.
VENUE_SELECTORS = """
(
  nwr["amenity"~"^(music|nightclub|concert_hall|events_venue|casino|public_hall|theatre|arts_centre)$"];
  nwr["leisure"="live_music_venue"];
  nwr["music:type"];
  nwr["theatre"="live"];
  nwr["amenity"~"^(bar|pub)$"];
);
"""

# Tags that make a bar/pub plausible as a music branch. A bar with none of
# these is a bar that happens to be in the bounding box; we keep it as a
# *candidate* but score it down.
MUSIC_SIGNALS = (
    "music:type", "live_music", "live_music_venue", "stage",
    "dance", "karaoke", "dj", "jazz", "band", "entertainment",
)


@dataclass
class Candidate:
    """A place we think might host shows, with the evidence for that claim."""

    name: str
    osm_type: str            # node | way | relation
    osm_id: int
    lat: float
    lon: float
    tags: dict = field(default_factory=dict)
    tile: str = ""

    # Is this a plausible music branch, or just a bar in the bbox?
    is_music_venue: bool = False
    score: int = 0
    reasons: list[str] = field(default_factory=list)

    @property
    def osm_url(self) -> str:
        return f"https://www.openstreetmap.org/{self.osm_type}/{self.osm_id}"

    def as_dict(self) -> dict:
        d = asdict(self)
        d["osm_url"] = self.osm_url
        return d


def _classify(tags: dict) -> tuple[bool, int, list[str]]:
    """Decide whether a place is a music branch. Returns (verdict, score, why).

    Kept separate and pure so the policy is testable without a network, and so
    a future version can change the policy without touching the fetch code.
    """
    reasons: list[str] = []
    score = 0

    amenity = tags.get("amenity", "")
    if tags.get("leisure") == "live_music_venue":
        score += 6
        reasons.append("leisure=live_music_venue")
    if tags.get("music:type"):
        score += 6
        reasons.append(f"music:type={tags['music:type']}")
    if tags.get("theatre") == "live":
        score += 5
        reasons.append("theatre=live")
    if amenity == "music":
        score += 6
        reasons.append("amenity=music")
    if amenity in ("concert_hall", "events_venue", "public_hall", "arts_centre"):
        score += 5
        reasons.append(f"amenity={amenity}")
    if amenity == "nightclub":
        score += 4
        reasons.append("amenity=nightclub")
    if amenity == "casino":
        # Real music, but often amplified/DJs and hard to crawl. Scored just
        # at the threshold: Graton Resort and Casino genuinely does book acts,
        # so excluding it outright would drop a real branch, but it should not
        # outrank a venue that states its music policy.
        score += 4
        reasons.append("amenity=casino (low confidence)")
    if amenity in ("bar", "pub"):
        score += 1
        reasons.append(f"amenity={amenity}")
    # `theatre` is not in the strong list above because a theatre in this town
    # may be straight drama, but Luther Burbank Center and Veterans Memorial
    # both run live music and neither carries a music tag. It sits at the
    # threshold rather than above it: discoverable, ranked below the venues
    # that assert music explicitly.
    if amenity == "theatre" and score == 0:
        score = 4
        reasons.append("amenity=theatre (unconfirmed live music)")

    # Signal tags on any of the above. These are what separate a venue that
    # hosts bands from one that only pours beer.
    signals = [k for k in MUSIC_SIGNALS if k in tags and k not in ("music:type",)]
    if signals:
        score += 3
        reasons.append("signals: " + ",".join(sorted(signals)))

    # An explicit "no music" beats every generic signal.
    if tags.get("music") == "no" or tags.get("live_music") == "no":
        score -= 4
        reasons.append("explicitly tagged no live music")

    return (score >= 4, score, reasons)


class OverpassError(RuntimeError):
    """The gazetteer did not answer. Never swallowed — see module docstring."""


class OverpassClient:
    """Minimal Overpass client with disk cache, tiling and honest partials."""

    def __init__(
        self,
        cache_dir: str | Path = ".cache/overpass",
        *,
        endpoints: tuple[str, ...] = OVERPASS_ENDPOINTS,
        min_interval_sec: float = 1.0,
        timeout_sec: float = 90,
        max_retries: int = 2,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.endpoints = endpoints
        self.min_interval_sec = min_interval_sec
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self._last_call = 0.0

    # ---------------------------------------------------------------- cache

    def _cache_path(self, query: str) -> Path:
        digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:20]
        return self.cache_dir / f"{digest}.json"

    def cached(self, query: str) -> dict | None:
        p = self._cache_path(query)
        if p.exists():
            try:
                return json.loads(p.read_text())
            except json.JSONDecodeError:
                p.unlink(missing_ok=True)
        return None

    def _store_cache(self, query: str, data: dict) -> None:
        self._cache_path(query).write_text(json.dumps(data))

    # ---------------------------------------------------------------- fetch

    def _throttle(self) -> None:
        gap = time.monotonic() - self._last_call
        if gap < self.min_interval_sec:
            time.sleep(self.min_interval_sec - gap)
        self._last_call = time.monotonic()

    def fetch(self, query: str, *, use_cache: bool = True) -> dict:
        """Run one Overpass query. Raises OverpassError if all retries fail."""
        if use_cache:
            hit = self.cached(query)
            if hit is not None:
                return hit

        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            for endpoint in self.endpoints:
                try:
                    self._throttle()
                    body = urllib.parse.urlencode({"data": query}).encode()
                    req = urllib.request.Request(
                        endpoint, data=body, headers={"User-Agent": USER_AGENT}
                    )
                    with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                    self._store_cache(query, data)
                    return data
                except urllib.error.HTTPError as exc:
                    last_err = exc
                    # 429 = rate limited: back off and stop hitting this mirror.
                    if exc.code in (429, 504):
                        time.sleep(5 * (attempt + 1))
                        break
                    continue
                except Exception as exc:      # noqa: BLE001 - want last reason
                    last_err = exc
                    continue
            if attempt < self.max_retries:
                time.sleep(4 * (attempt + 1))

        raise OverpassError(f"all endpoints failed after {self.max_retries + 1} tries: {last_err}")

    # ---------------------------------------------------------------- tiles

    @staticmethod
    def tiles(bbox: tuple[float, float, float, float], max_deg: float = 0.06) -> list[str]:
        """Split a bbox into bboxes of at most `max_deg` on a side.

        A 0.24 x 0.30 box of bars is the difference between a fast query and a
        504. Splitting is not an optimisation, it is what makes the area
        queryable at all.
        """
        south, west, north, east = bbox
        rows = max(1, int((north - south) / max_deg) + 1)
        cols = max(1, int((east - west) / max_deg) + 1)
        out: list[str] = []
        for r in range(rows):
            for c in range(cols):
                s = south + (north - south) * r / rows
                n = south + (north - south) * (r + 1) / rows
                w = west + (east - west) * c / cols
                e = west + (east - west) * (c + 1) / cols
                # A hair of overlap: a venue exactly on a tile seam should not
                # be missed because rounding put it outside both tiles.
                out.append(f"{s:.5f},{w:.5f},{n + 1e-4:.5f},{e + 1e-4:.5f}")
        return out

    def discover_area(
        self,
        bbox: tuple[float, float, float, float],
        *,
        selectors: str = VENUE_SELECTORS,
        max_deg: float = 0.06,
        require_name: bool = True,
        sleep_between_tiles: float = 1.0,
    ) -> tuple[list[Candidate], list[str]]:
        """Find candidate venues in a bbox. Returns (candidates, failed_tiles).

        `failed_tiles` is part of the signature on purpose. A caller that
        ignores it will believe it has complete coverage of an area that was
        only partly scanned, and that is the failure this project cannot
        afford.
        """
        tile_boxes = self.tiles(bbox, max_deg)
        by_key: dict[tuple[str, int], Candidate] = {}
        failures: list[str] = []

        for i, box in enumerate(tile_boxes):
            query = f"[out:json][timeout:60];{selectors}({box});out tags center;"
            try:
                data = self.fetch(query)
            except OverpassError as exc:
                failures.append(f"{box}: {exc}")
                continue

            for el in data.get("elements", []):
                tags = el.get("tags") or {}
                name = tags.get("name")
                if require_name and not name:
                    continue
                lat = el.get("lat") or (el.get("center") or {}).get("lat")
                lon = el.get("lon") or (el.get("center") or {}).get("lon")
                if lat is None or lon is None:
                    continue
                key = (el.get("type", "node"), int(el.get("id", 0)))
                if key in by_key:
                    continue    # seen on a previous tile's overlap edge
                verdict, score, reasons = _classify(tags)
                by_key[key] = Candidate(
                    name=name or f"(unnamed {el.get('type')} {el.get('id')})",
                    osm_type=key[0],
                    osm_id=key[1],
                    lat=float(lat),
                    lon=float(lon),
                    tags=tags,
                    tile=box,
                    is_music_venue=verdict,
                    score=score,
                    reasons=reasons,
                )
            if i < len(tile_boxes) - 1 and sleep_between_tiles:
                time.sleep(sleep_between_tiles)

        candidates = sorted(by_key.values(), key=lambda c: (-c.score, c.name.lower()))
        return candidates, failures


def candidates_from_overpass(data: dict, *, tile: str = "") -> list[Candidate]:
    """Parse a raw Overpass response. Split out so it can be tested offline."""
    out: list[Candidate] = []
    for el in data.get("elements", []):
        tags = el.get("tags") or {}
        name = tags.get("name")
        if not name:
            continue
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        verdict, score, reasons = _classify(tags)
        out.append(
            Candidate(
                name=name,
                osm_type=el.get("type", "node"),
                osm_id=int(el.get("id", 0)),
                lat=float(lat),
                lon=float(lon),
                tags=tags,
                tile=tile,
                is_music_venue=verdict,
                score=score,
                reasons=reasons,
            )
        )
    return out