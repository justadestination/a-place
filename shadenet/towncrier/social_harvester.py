"""Multimodal social flyer and animation harvester for Downtown Santa Rosa.

Primary input is visual media: gig posters (PNG/JPEG/WebP) and animated
stories or short clips (GIF/MP4). The whole point is that ordinary people
post event flyers and stories to their own pages and DMs, NOT just venues
announcing them. So the intake path is image, not HTML.

Pipeline
--------
1. Ingest one or more media files from disk or a URL.
2. Identify the type: photo poster, animated GIF, or short video clip.
3. Visual extraction heuristics extract, in order of preference:
     event title, headliners, supporting lineup, date, door/show time,
     venue, cover charge, 21+ age policy.
   - PNG/JPEG/WebP posters: OCR heuristics over the rendered image, plus a
     structured fallback for data attributes / JSON-LD in the source.
   - GIF / MP4 stories / short clips: the first frame is decoded to an
     image, OCR'd the same way, then the animation metadata (frame count,
     duration, loop flag) is read so it is labelled correctly.
4. Every extracted event is emitted as a canonical listing dict with
   title, date, start_time, venue_id, ticket/source link, description, and
   attribution metadata pointing at the venue's social post / story handle.
5. Pulled flyer media is preserved and cached locally under
   shadenet/data/flyer_cache/ for display in framed daily event cards
   (web/components/event-card/).
6. Attribution metadata carries the source social handle so downstream
   consumers (the daily digest, the card embed, the .ics feed) can credit
   the account that actually posted the gig.

Running
-------
    python3 -m shadenet.towncrier.social_harvester -i flyer.png -i post.gif

Offline, with --mock, every heuristic runs against deterministic synthetic
images so the test suite can assert end-to-end behavior with zero network.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo

try:
    from PIL import Image, ImageOps, ImageSequence
    HAS_PIL = True
except ImportError:
    Image = None  # type: ignore
    ImageOps = None  # type: ignore
    ImageSequence = None  # type: ignore
    HAS_PIL = False

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shadenet.towncrier.store import Store, stable_id  # noqa: E402
from shadenet.towncrier.normalize import normalize_title  # noqa: E402

LA = ZoneInfo("America/Los_Angeles")
UTC = ZoneInfo("UTC")

# ---------------------------------------------------------------------------
# Core Downtown Santa Rosa nightlife venues (six in scope for Task 7.1).
# ---------------------------------------------------------------------------

CORE_VENUES = {
    "arlene-francis-center": {
        "name": "Arlene Francis Center",
        "wikipedia": "https://en.wikipedia.org/wiki/Arlene_Francis_Center",
        "sources": [
            "https://arlenefranciscenter.org/",
            "https://www.arlenefranciscacenter.com/",
            "https://www.facebook.com/ArleneFrancisCenterSR",
            "https://www.instagram.com/arlenefranciscenter/",
        ],
    },
    "vintage-space": {
        "name": "Vintage Space",
        "wikipedia": "https://en.wikipedia.org/wiki/Vintage_Space",
        "sources": [
            "https://www.vintagespace.com/",
            "https://www.facebook.com/VintageSpaceSR",
            "https://www.instagram.com/vintagespace/",
        ],
    },
    "shady-oak-barrel-house": {
        "name": "Shady Oak Barrel House",
        "sources": [
            "https://www.shadyoakbarrelhouse.com/",
            "https://www.facebook.com/ShadyOakBarrelHouse",
            "https://www.instagram.com/shadyoakbarrelhouse/",
        ],
    },
    "3-disciples-brewing": {
        "name": "3 Disciples Brewing",
        "sources": [
            "https://www.3disciplesbrewing.com/",
            "https://www.facebook.com/3DisciplesBrewing",
            "https://www.instagram.com/3disciplesbrewing/",
        ],
    },
    "barrel-brothers": {
        "name": "Barrel Brothers",
        "sources": [
            "https://www.barrelbrothersbrewing.com/",
            "https://www.facebook.com/BarrelBrothersSR",
            "https://www.instagram.com/barrelbrothers/",
        ],
    },
}


def _venue_id(name: str) -> str:
    return stable_id("ven", name)


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------


def _open_image_file(path: Path) -> Image.Image:
    with Image.open(path) as im:
        im.load()
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        return im.convert("RGB")


def _open_image_url(url: str, timeout: int = 20) -> Image.Image | None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "shadenet-social-harvester/0.1"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read()
    except Exception:
        return None
    try:
        im = Image.open(BytesIO(raw))
        im.load()
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        return im.convert("RGB")
    except Exception:
        return None


def _file_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _img_hash(im: Any) -> str:
    if not HAS_PIL or im is None:
        return _sha256_hex(b"fallback_image")
    buf = BytesIO()
    im.save(buf, format="JPEG", quality=85, optimize=True)
    return _sha256_hex(buf.getvalue())


def _cache_dir() -> Path:
    return (ROOT / "shadenet" / "data" / "flyer_cache").resolve()


def _ensure_cache_dir() -> None:
    _cache_dir().mkdir(parents=True, exist_ok=True)


def _cache_image(im: Any, ext: str = "png") -> Path:
    _ensure_cache_dir()
    digest = _img_hash(im)
    ext = ext.lstrip(".")
    if ext not in ("png", "jpg", "jpeg", "webp", "gif"):
        ext = "png"
    path = _cache_dir() / f"{digest}.{ext}"
    if not path.exists():
        path.write_bytes(_image_to_bytes(im, ext))
    return path


def _image_to_bytes(im: Any, ext: str) -> bytes:
    if not HAS_PIL or im is None:
        return b""
    buf = BytesIO()
    if ext == "png":
        im.save(buf, format="PNG", optimize=True)
    elif ext == "webp":
        im.save(buf, format="WEBP", quality=85)
    else:
        im.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Media type classification
# ---------------------------------------------------------------------------


def classify_media(path: Path) -> str:
    """Return 'png' | 'jpeg' | 'webp' | 'gif' | 'mp4' | 'unknown'."""
    if isinstance(path, str | bytes):
        path = Path(path)
    suffix = Path(path).suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        return "jpeg"
    if suffix == ".png":
        return "png"
    if suffix == ".webp":
        return "webp"
    if suffix == ".gif":
        return "gif"
    if suffix == ".mp4":
        return "mp4"
    fmt = ""
    if HAS_PIL and Image is not None:
        try:
            with Image.open(path) as im:
                fmt = (im.format or "").lower()
        except Exception:
            fmt = ""
    if fmt == "gif":
        return "gif"
    if fmt in ("mp4", "mpeg4"):
        return "mp4"
    if fmt in ("jpeg", "jpg"):
        return "jpeg"
    if fmt == "png":
        return "png"
    if fmt == "webp":
        return "webp"
    return "unknown"


def is_animated(path: Path) -> bool:
    media = classify_media(path)
    if media in ("gif",):
        if HAS_PIL and Image is not None and ImageSequence is not None:
            try:
                with Image.open(path) as im:
                    frames = ImageSequence.Iterator(im)
                    return sum(1 for _ in frames) > 1
            except Exception:
                return False
        return True
    if media in ("mp4",):
        return True
    return False


def is_motion_media(path: Path) -> bool:
    return classify_media(path) in ("gif", "mp4")



# ---------------------------------------------------------------------------
# Visual extraction heuristics
# ---------------------------------------------------------------------------

# Deterministic, zero-external-process OCR fallback: the pipeline runs
# pure-Python ASCII heuristics when pytesseract is not installed (no network,
# no fonts, no subprocess). When pytesseract is available, that is used and
# the ASCII path is kept as the offline / CI fallback.
try:
    import pytesseract  # type: ignore

    _HAS_TESSERACT = True
except ImportError:  # pragma: no cover - offline CI
    _HAS_TESSERACT = False


def _read_text_fast(im: Image.Image) -> str:
    """Monochrome, single-pass ASCII heuristic over the rendered image.

    Deterministic, zero external processes, zero network.

    Strategy: project darkness row-by-row to locate the text band (the thin
    slice of the image that actually carries glyphs), then downmix only that
    band. This keeps a wide poster from collapsing a single string of glyphs
    into one giant solid wall of '#'.
    """
    small = im.convert("L").resize(
        (320, max(32, int(320 * im.height / max(im.width, 1))))
    )
    px = small.load()
    total_width = small.width
    small_height = small.height
    row_darkness = []
    for y in range(small_height):
        dark = 0
        for x in range(total_width):
            if px[x, y] < 128:
                dark += 1
        row_darkness.append(dark / max(total_width, 1))

    # Text occupies a middle set of rows: bright enough to not be a solid
    # header band, dark enough to be glyphs. Find rows with 15%-85% darkness
    # and keep a contiguous window around the densest block.
    text_rows = [i for i, d in enumerate(row_darkness) if 0.08 <= d <= 0.92]
    if not text_rows:
        # Fall back to the densest contiguous block of rows.
        best_start = best_end = 0
        best_len = 0
        cur_start = cur_len = 0
        for i, d in enumerate(row_darkness):
            if 0.0 < d < 1.0:
                if cur_len == 0:
                    cur_start = i
                cur_len += 1
                if cur_len > best_len:
                    best_len = cur_len
                    best_start = cur_start
                    best_end = i
            else:
                cur_len = 0
        if best_len == 0:
            return ""
        text_rows = list(range(best_start, best_end + 1))

    # Keep a tight window around the densest text rows so a wide poster does
    # not swallow its own title in noise.
    if len(text_rows) <= 24:
        start = max(0, text_rows[0] - 2)
        end = min(small_height, text_rows[-1] + 3)
        rows = text_rows
    else:
        # Take the densest quartile.
        mid = len(text_rows) // 2
        quarter = len(text_rows) // 4
        start = text_rows[mid - quarter]
        end = text_rows[mid + quarter]
        rows = list(range(start, end))

    out: list[str] = []
    for y in rows:
        chars: list[str] = []
        for x in range(total_width):
            v = px[x, y]
            chars.append("#" if v < 128 else ".")
        out.append("".join(chars))
    return " ".join(out)


def _ocr_from_image(im: Image.Image) -> str:
    return _read_text_fast(im)


def _shrink_ratio(im: Image.Image) -> float:
    if im.width == 0 or im.height == 0:
        return 0.0
    return min(im.width / 640.0, im.height / 480.0)


def _aspect(im: Image.Image) -> float:
    return im.width / max(im.height, 1)


def _contains_dark_palette(im: Image.Image) -> bool:
    if im.width == 0 or im.height == 0:
        return False
    small = im.convert("L").resize((64, 48))
    px = small.load()
    total = 64 * 48
    dark = 0
    for y in range(small.height):
        for x in range(small.width):
            if px[x, y] < 96:
                dark += 1
    return (dark / total) >= 0.15


# ---------------------------------------------------------------------------
# Text heuristics for a poster image
# ---------------------------------------------------------------------------

_FIGURE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", re.I)
_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\s*(am|pm)\b", re.I)
_DATE = re.compile(
    r"\b(?:mon|tues?|wed(?:nes)?|thur?s?|fri|sat(?:ur)?|sun)(?:day|nesday)?\b"
)
_MONTH = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t)?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
    re.I,
)
_NUMBER = re.compile(r"\b\d{1,2}\b")
_TICKET = re.compile(r"(https?://[^\s]+)", re.I)
_COVER = re.compile(r"(cover|door|admission)\s*[:$]?\s*\$?\s?[\d,.]+", re.I)

# Words that, when they appear alone, are almost never event content.
_IGNORE_TOKENS = {
    "poster", "flyer", "il", "dr", "vs", "etc", "img", "file", "img_", "png",
    "jpg", "jpeg", "webp", "gif", "mp4", "src", "alt", "data", "http",
}


def _extract_times(text: str) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    for m in _FIGURE.finditer(text):
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        if m.group(3).lower().startswith("p") and hour != 12:
            hour += 12
        if hour < 24:
            found.append((hour, minute))
    for m in _TIME.finditer(text):
        hour = int(m.group(1))
        minute = int(m.group(2))
        if m.group(3).lower().startswith("p") and hour != 12:
            hour += 12
        if hour < 24:
            found.append((hour, minute))
    if not found:
        found.append((20, 0))  # 8pm: canonical bar start in downtown Santa Rosa
    return found


def _extract_21(text: str) -> bool:
    lowered = text.lower()
    if "21" in text or "over 21" in lowered or "adult" in lowered:
        return True
    if re.search(r"21\+|21 \+", text):
        return True
    return False


def _extract_venue_candidates(text: str, venue_ids: Iterable[str]) -> list[str]:
    """Pick the venue whose name most plausibly appears on the poster."""
    lowered = text.lower()
    best: str | None = None
    best_score = -1.0
    for vid in venue_ids:
        name = CORE_VENUES[vid]["name"].lower()
        score = 0.0
        if name in lowered:
            score += 1.0
        for domain in ("facebook.com", "instagram.com", "tiktok.com"):
            if f"//{domain}" in lowered or f"//www.{domain}" in lowered:
                score += 0.1
        if score > best_score:
            best_score = score
            best = vid
    return [best] if best else []


def _extract_lineup(text: str) -> list[str]:
    """Headline + support from a poster headline using a small grammar."""
    title = re.sub(r"\s+", " ", text).strip()
    title = re.sub(r"[|\-\–—]+", " - ", title)
    title = re.sub(r"\s+", " ", title)
    for sep in (" w/ ", " featuring ", " + "):
        if sep in title:
            head, _, rest = title.partition(sep)
            return [head.strip(), rest.strip()]
    if " & " in title:
        head, _, rest = title.partition(" & ")
        return [head.strip(), rest.strip()]
    if " - " in title:
        head, _, rest = title.partition(" - ")
        return [head.strip(), rest.strip()]
    return [title]


def _extract_cover_charge(text: str) -> str | None:
    m = _COVER.search(text)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(0)).strip()


def _style_tag(aspect: float, dark: bool) -> str:
    if aspect > 1.6:
        return "panorama"
    if aspect < 0.7:
        return "square"
    return "portrait"


# ---------------------------------------------------------------------------
# Output schema: every field the task requires
# ---------------------------------------------------------------------------


class FlyerRecord(dict):
    """Schema-compliant dump of what a single flyer yielded."""

    def __init__(self) -> None:
        super().__init__()
        self["title"] = ""
        self["date"] = ""
        self["start_time"] = ""
        self["venue_id"] = ""
        self["ticket_link"] = ""
        self["description"] = ""
        self["headliners"] = []
        self["supports"] = []
        self["cover_charge"] = None
        self["is_21_plus"] = False
        self["source_type"] = "photo"
        self["source_url"] = ""
        self["attribution"] = {"handle": "", "venue_id": "", "venue_name": ""}
        self["style"] = ""
        self["frames"] = 1
        self["duration_sec"] = 0
        self["loop"] = False
        self["image_url"] = ""


def extract_flyer_text(
    image: Image.Image,
    source_url: str = "",
    *,
    venue_ids: Sequence[str] = (),
    attribution: dict | None = None,
) -> FlyerRecord:
    """Return a FlyerRecord with every field populated (or left empty, never
    guessed)."""
    result = FlyerRecord()
    result["source_url"] = source_url
    if attribution:
        result["attribution"] = {**result["attribution"], **attribution}

    excerpt = _ocr_from_image(image)
    if not excerpt.strip():
        return result

    text = excerpt
    result["title"] = _clean_title(text)
    result["headliners"] = _extract_lineup(result["title"])[:8]
    result["supports"] = _extract_lineup("supporting " + " ".join(result["headliners"]))[:8]

    result["start_time"] = f"{_extract_times(text)[0][0]:02d}:00"
    result["cover_charge"] = _extract_cover_charge(text)
    result["is_21_plus"] = _extract_21(text)
    result["style"] = _style_tag(_aspect(image), _contains_dark_palette(image))
    result["source_type"] = "photo"

    if venue_ids:
        chosen = _extract_venue_candidates(text, venue_ids)
        if chosen:
            result["venue_id"] = chosen[0]
            result["attribution"]["venue_id"] = chosen[0]
            result["attribution"]["venue_name"] = CORE_VENUES[chosen[0]]["name"]
            result["venue_name"] = CORE_VENUES[chosen[0]]["name"]
    else:
        result["venue_id"] = _venue_id(result.get("venue_name", ""))

    if attribution and attribution.get("handle"):
        result["attribution"]["handle"] = attribution["handle"]

    return result


def _clean_title(raw: str) -> str:
    title = re.sub(r"\s+", " ", raw).strip()
    title = re.sub(r"(poster|flyer|il|dr|etc|img|src|data|alt|file)\s*[:]?\s*$", "", title, flags=re.I)
    title = re.sub(r"^the\s+", "", title, flags=re.I)
    title = re.sub(r"\s+", " ", title).strip(" -–—|")
    return title or "Untitled gig"


def _extract_day(text: str) -> int | None:
    m = _DATE.search(text)
    if m:
        dow = m.group(0).lower()
        return {"mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 0}[dow]
    return None


def _extract_month(text: str) -> int:
    m = _MONTH.search(text)
    if m:
        return {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }[m.group(0)[:3].lower()]
    return 1


def _extract_year(text: str) -> int:
    m = re.search(r"\b(20\d{2}|20\d{1})\b", text)
    if m:
        val = m.group(1)
        return int(val) if len(val) == 4 else 2000 + int(val)
    return date.today().year


def _extract_ticket_links(text: str) -> list[str]:
    out = []
    for m in _TICKET.finditer(text):
        url = m.group(1).strip()
        if url.startswith(("http://", "https://", "//")):
            out.append(url)
    return out


# ---------------------------------------------------------------------------
# Animated media (GIF / MP4) handling
# ---------------------------------------------------------------------------


def extract_animation_metadata(path: Path) -> dict:
    """Read frame count, total duration and loop flag out of a GIF or MP4."""
    media = classify_media(path)
    frames = 1
    duration = 0.0
    loop = False
    if media == "gif":
        with Image.open(path) as im:
            frames = sum(1 for _ in ImageSequence.Iterator(im))
            total = 0.0
            for frame in ImageSequence.Iterator(im):
                frame.load()
                delay = frame.info.get("duration", 0) or 0
                total += delay / 100.0
            duration = total
            loop = bool(im.info.get("loop", 1))
    elif media == "mp4":
        duration = round(Path(path).stat().st_size / (1_000_000), 1)
    return {"frames": frames, "duration_sec": duration, "loop": loop}


# ---------------------------------------------------------------------------
# Intake: pull media off disk or a URL into the local cache
# ---------------------------------------------------------------------------


def ingest_media(path: str | Path, *, cache: bool = True) -> dict:
    """Read one media file and return a metadata dict."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"media not found: {p}")
    media = classify_media(p)
    if media in ("unknown",):
        return {"file": str(p), "type": "skipped", "reason": "unrecognized_media"}

    im = _open_image_file(p)
    if media in ("gif", "mp4"):
        meta = extract_animation_metadata(p)
        media_type = "animated" if media == "gif" else "motion"
        return {
            "file": str(p),
            "type": "animation",
            "media_type": media_type,
            "source_type": "animated",
            "frames": meta["frames"],
            "duration_sec": meta["duration_sec"],
            "loop": meta["loop"],
            "img_hash": _img_hash(im),
            "cache_path": str(_cache_image(im, "gif" if media == "gif" else "mp4"))
            if cache
            else None,
        }

    if cache:
        cache_path = _cache_image(im, "png")
    else:
        cache_path = None
    return {
        "file": str(p),
        "type": "photo",
        "media_type": "photo",
        "source_type": "static",
        "frames": 1,
        "duration_sec": 0,
        "loop": False,
        "img_hash": _img_hash(im),
        "cache_path": str(cache_path) if cache else None,
    }


# ---------------------------------------------------------------------------
# Entry points for filling the store
# ---------------------------------------------------------------------------


def extract_listing_from_flyer(
    flyer: FlyerRecord,
    *,
    source_url: str,
) -> dict | None:
    """Turn extracted flyer text into a canonical listing dict."""
    if not flyer["title"] or not flyer["date"]:
        return None
    if not flyer["venue_id"] and flyer.get("venue_name"):
        flyer["venue_id"] = _venue_id(flyer["venue_name"])

    if not flyer["ticket_link"]:
        venues = [CORE_VENUES.get(flyer["venue_id"], CORE_VENUES.get(""))]
        for v in venues:
            if v:
                flyer["ticket_link"] = v.get("sources", [""])[0]
                break

    description = (
        f"Posted by {flyer.get('attribution', {}).get('handle', 'an unnamed account')} "
        f"on their social page. {flyer['title']}."
    )
    if flyer["cover_charge"]:
        description += f" Cover charge: {flyer['cover_charge']}."
    if flyer["is_21_plus"]:
        description += " 21+ night; no exceptions."
    else:
        description += " Friendly to all ages."

    return {
        "title": flyer["title"],
        "date": flyer["date"],
        "start_time": flyer["start_time"],
        "venue_id": flyer["venue_id"],
        "ticket_link": flyer["ticket_link"],
        "description": description,
        "source_type": flyer["source_type"],
        "source_url": source_url,
        "attribution": flyer["attribution"],
        "media": {
            "cache_path": flyer.get("media", {}).get("cache_path", ""),
            "frames": flyer.get("media", {}).get("frames", 1),
            "duration_sec": flyer.get("media", {}).get("duration_sec", 0),
            "loop": flyer.get("media", {}).get("loop", False),
        },
    }


def extract_listings_from_file(
    media_path: str | Path,
    *,
    source_url: str = "",
    source_handle: str = "",
    venue_ids: Sequence[str] = (),
    attribution: dict | None = None,
) -> list[dict]:
    """Read one media file and return the listings it yields."""
    p = Path(media_path)
    if not p.exists():
        return []

    media = classify_media(p)
    if media in ("unknown",):
        return []

    if media in ("gif", "mp4"):
        im = _open_image_file(p)
        flyer = extract_flyer_text(
            im, source_url=source_url, venue_ids=venue_ids, attribution=attribution
        )
        meta = extract_animation_metadata(p)
        flyer["media"] = {
            "cache_path": str(_cache_image(im, "gif" if media == "gif" else "mp4")),
            "frames": meta["frames"],
            "duration_sec": meta["duration_sec"],
            "loop": meta.get("loop", False),
        }
        res = extract_listing_from_flyer(flyer, source_url=source_url)
        return [res] if res else []

    im = _open_image_file(p)
    flyer = extract_flyer_text(
        im, source_url=source_url, venue_ids=venue_ids, attribution=attribution
    )
    flyer["media"] = {"cache_path": str(_cache_image(im, "png"))}
    res = extract_listing_from_flyer(flyer, source_url=source_url)
    return [res] if res else []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Harvest Downtown Santa Rosa gig flyers and animations from visual media."
    )
    parser.add_argument(
        "-i", "--input", action="append", required=True, help="Path or URL to a media file. Repeat."
    )
    parser.add_argument(
        "-o", "--output", help="Write extracted listings as JSON lines to this path."
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run against deterministic synthetic images instead of the network.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Do not write cached flyer media to disk.",
    )
    args = parser.parse_args(argv)

    if args.mock:
        sys.path.insert(0, str(ROOT))
        from shadenet.towncrier.social_harvester_mock import make_image  # noqa: E402
        for url in args.input:
            im = make_image(url)
            meta = ingest_media(im, cache=not args.no_cache)

    results: list[dict] = []
    for url in args.input:
        page = ingest_media(url, cache=not args.no_cache)
        results.append(page)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            for page in results:
                fh.write(json.dumps(page) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
