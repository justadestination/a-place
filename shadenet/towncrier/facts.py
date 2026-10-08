"""Enrichment: harvesting cited facts from a venue's own pages.

`discover.py` finds the branches; this fills them in. Discovery from OSM gives
a name and a location, and in this area that is genuinely all you get — only
about a quarter of venues carry a phone in OSM at all. The phone number is
usually on the venue's own website, in one of a small number of predictable
places.

## The sources of truth, in trust order

1. **schema.org JSON-LD** on the venue's own site. A `<script
   type="application/ld+json">` block with `telephone` is the venue stating
   its own phone number in a machine-readable form. Highest confidence, and it
   is usually one parse rather than a guess.
2. **`tel:` and `mailto:` hrefs** anywhere in the markup. Explicit, authored,
   and unambiguous — a human put that link there on purpose.
3. **Microdata / visible-text patterns.** Weaker, and treated as such.

Everything extracted carries the URL it came from, because `add_item` refuses
facts without provenance and this is where that provenance is born.

## What this deliberately does not do

It does not guess. There is no "the phone is probably the one in the footer of
the page that matches the area code". Where a page states a phone number, we
take it and cite the page. Where it does not, we record nothing and
`venue_dossier` reports `not_found` — a visible gap beats a plausible wrong
number, because a wrong number is indistinguishable from a right one until
somebody dials it.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Iterable

from .entities import (
    KIND_ADDRESS,
    KIND_EMAIL,
    KIND_HOURS,
    KIND_PHONE,
    KIND_SOCIAL,
    KIND_WEBSITE,
    add_item,
    normalize_item,
)

USER_AGENT = "towncrier/0.1 (local event research; contact: operator)"

# A US phone number, in the shapes venues actually write. Deliberately
# requires an area code: a bare 7-digit local number is ambiguous and we would
# be guessing which area code applies.
PHONE_RE = re.compile(
    r"(?:(?:\+?1[\s.\-]?)?\(?([2-9]\d{2})\)?[\s.\-]?([2-9]\d{2})[\s.\-]?(\d{4}))"
)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]{2,}")

# Social handles, keyed by the kind we record them under. Matching the domain
# is more reliable than matching a string, because "@theroyal" appears in
# prose constantly and means nothing.
SOCIAL_DOMAINS = {
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "instagram.com": "instagram",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "tiktok.com": "tiktok",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "bandcamp.com": "bandcamp",
    "spotify.com": "spotify",
    "linktr.ee": "linktree",
}

# Hours in the two shapes venues publish them: JSON-LD openingHours strings,
# and free text like "Mon: CLOSED  Tues - Fri: 3-11 pm".
#
# The value group is lazy and bounded by a lookahead for the *next* day token.
# A greedy `[^;\n]{1,40}` swallows what follows, so "Mon: CLOSED Tues - Fri:
# 3-11 pm" parses as a single Monday row whose hours are the string "CLOSED
# Tues - Fri: 3-11 pm Sat: 2-11 pm" -- which is not hours, and which then gets
# published as though it were.
HOURS_JSONLD_KEYS = ("openingHours", "openingHoursSpecification")
HOURS_FREEFORM_RE = re.compile(
    r"(?P<day>[A-Za-z]{3,9}(?:\s*-\s*[A-Za-z]{3,9})?)\s*[:\-]\s*"
    r"(?P<val>[^;\n]{1,40}?)"
    r"(?=\s*[A-Za-z]{3,9}\s*(?:[:\-]|$)|\s*$)",
    re.I,
)


# A US postal address in the shape venues actually write it, typically with the
# city/state/zip on the following line. Anchored on the zip, which is the one
# part that is unambiguous, and required to be a plausible 5-digit US zip.
# Addresses are the fact most often present as bare text on a small venue's
# site -- Shady Oak publishes its street, city and zip as three separate
# paragraphs with no markup at all -- so a JSON-LD-only extractor finds no
# address for exactly the venues that need it most.
ADDRESS_ZIP_RE = re.compile(
    r"(?P<street>\d{1,6}\s+[A-Za-z0-9][A-Za-z0-9 .'#/\\-]{1,60}?"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Way|Lane|Ln|Drive|Dr|Court|Ct"
    r"|Place|Pl|Highway|Hwy|Square|Sq|Terrace|Ter|Placeway|Pkwy|Parkway)\b\.?)"
    r"[,\s]*"
    r"(?P<city>[A-Za-z][A-Za-z .'-]{1,40}?)"
    r"[,\s]+(?P<state>[A-Z]{2})\.?\s+(?P<zip>\d{5})",
    re.I,
)


def _find_addresses(text: str) -> list[tuple[str, str]]:
    """Return [(value, excerpt)] for postal addresses in visible text."""
    out: list[tuple[str, str]] = []
    for m in ADDRESS_ZIP_RE.finditer(text):
        street = re.sub(r"\s+", " ", m.group("street")).strip(" ,.")
        city = re.sub(r"\s+", " ", m.group("city")).strip(" ,.")
        state = m.group("state").upper()
        zipc = m.group("zip")
        if not street or not city:
            continue
        # A street fragment of one or two characters is a regex artefact, not
        # an address ("5 A St" is fine; "5 A" is not).
        if len(street) < 4:
            continue
        value = f"{street}, {city}, {state} {zipc}"
        lo, hi = max(0, m.start() - 30), min(len(text), m.end() + 30)
        out.append((value, text[lo:hi]))
    return out


def _http_get(url: str, *, timeout: int = 30) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.status, raw.decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception:
        return 0, ""


class _LinkHarvester(HTMLParser):
    """Collect hrefs and the text that labels them.

    `handle_data` exists because venues put a phone number in visible text
    next to the word "CALL US" without making it a link — the Shady Oak page
    does exactly that. A link-only extractor gets nothing from those sites.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.hrefs.append(v)

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(self.text_parts)


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


# Page and file objects carry a url that is not the venue's website.
_URL_SKIP_TYPES = {
    "webpage", "contactpage", "aboutpage", "checkoutpage", "collectionpage",
    "imageobject", "searchaction", "entrypoint", "website", "breadcrumblist",
    "listitem", "faqpage", "question", "answer", "sitenavigationelement",
}


def _ld_type_names(node: dict) -> set[str]:
    raw = node.get("@type") or []
    if isinstance(raw, str):
        raw = [raw]
    return {
        item.split("/")[-1].split(":")[-1].lower()
        for item in raw if isinstance(item, str)
    }


def _find_jsonld(html: str) -> list[dict]:
    """Every JSON-LD object in the document, flattened through @graph."""
    out: list[dict] = []
    for raw in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.I | re.S,
    ):
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue    # malformed JSON-LD is common and not worth guessing at
        for node in _iter_ld_nodes(data):
            out.append(node)
    return out


def _iter_ld_nodes(data) -> Iterable[dict]:
    if isinstance(data, list):
        for item in data:
            yield from _iter_ld_nodes(item)
    elif isinstance(data, dict):
        if "@graph" in data:
            yield from _iter_ld_nodes(data["@graph"])
        # Yield any dict that carries at least one fact we care about.
        # Nested objects count too: a ContactPage often puts telephone,
        # address, and sameAs on mainEntity rather than on itself.
        interesting = {
            "telephone", "email", "address", "openingHours",
            "openingHoursSpecification", "name", "url", "sameAs",
        }
        if interesting & set(data.keys()):
            yield data
        for key, value in data.items():
            if key == "@graph" or not isinstance(value, (dict, list)):
                continue
            yield from _iter_ld_nodes(value)


def _ld_address(node: dict) -> str | None:
    addr = node.get("address")
    if isinstance(addr, str):
        return addr.strip() or None
    if not isinstance(addr, dict):
        return None
    parts = [
        addr.get("streetAddress"),
        addr.get("addressLocality"),
        addr.get("addressRegion"),
        addr.get("postalCode"),
    ]
    parts = [str(p) for p in parts if p]
    return ", ".join(parts) or None


def _ld_hours(node: dict) -> str | None:
    """Human-readable opening hours, or None.

    JSON-LD hours come in a dozen shapes (`openingHours: "Mo-Fr 17:00-23:00"`,
    a list, or a full `openingHoursSpecification` tree). We render rather than
    parse, because we only need something a human can read next to a source.
    """
    val = node.get("openingHours")
    if isinstance(val, str) and val.strip():
        return " ".join(val.split())
    if isinstance(val, list) and val:
        parts = [str(v).strip() for v in val if str(v).strip()]
        if parts:
            return "; ".join(parts)

    spec = node.get("openingHoursSpecification")
    rows: list[str] = []
    if isinstance(spec, dict):
        spec = [spec]
    if isinstance(spec, list):
        for entry in spec:
            if not isinstance(entry, dict):
                continue
            day = entry.get("dayOfWeek")
            day = "/".join(day) if isinstance(day, list) else (day or "?")
            op = entry.get("opens") or ""
            cl = entry.get("closes") or ""
            span = f"{op}-{cl}".strip("-") if (op or cl) else ""
            if entry.get("opens") == "00:00" and entry.get("closes") == "00:00":
                span = "closed"
            if span:
                rows.append(f"{day}: {span}")
    return "; ".join(rows) or None


def extract_facts(url: str, html: str) -> list[dict]:
    """Every fact we can support from one page.

    Returns dicts of {kind, value, display, excerpt, method}. Does not touch
    the database — kept pure so it can be tested against saved fixtures, and
    so the caller decides what counts as a source worth citing.
    """
    facts: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def emit(kind: str, value: str, display: str, excerpt: str, method: str) -> None:
        if not value:
            return
        # Dedup on the *normalized* value, so the several ways a venue writes
        # one phone number collapse to a single fact. Deduping on the raw
        # string would make "+1 707-543-1500" and "(707) 543-1500" two facts,
        # which then register as a two-way conflict -- a fabricated dispute
        # about a number the venue never disputed.
        key = (kind, normalize_item(kind, value))
        if not key[1]:
            return
        if key in seen:
            return
        seen.add(key)
        facts.append({"kind": kind, "value": value, "display": display,
                      "excerpt": excerpt.strip()[:300], "method": method})

    # ---- 1. JSON-LD: the venue stating its own facts
    #
    # Ordered by trust, and `emit` short-circuits: the first (most trustworthy)
    # statement of a normalized value wins the display text, and later ones
    # only add a corroborating citation. This is why "+1-707-543-1500",
    # "+17075431500" and "(707) 543-1500" produce one phone row and not three
    # -- dedup has to happen on the *normalized* value, not the raw string,
    # or the three spellings of one number look like a three-way conflict.
    for node in _find_jsonld(html):
        tel = node.get("telephone")
        if isinstance(tel, list):
            tel = tel[0] if tel else None
        if isinstance(tel, str) and tel.strip():
            emit(KIND_PHONE, tel.strip(), tel.strip(), f"JSON-LD telephone: {tel}", "jsonld")

        mail = node.get("email")
        if isinstance(mail, str) and "@" in mail:
            emit(KIND_EMAIL, mail.strip(), mail.strip(), f"JSON-LD email: {mail}", "jsonld")

        addr = _ld_address(node)
        if addr:
            emit(KIND_ADDRESS, addr, addr, f"JSON-LD address: {addr}", "jsonld")

        hours = _ld_hours(node)
        if hours:
            emit(KIND_HOURS, hours, hours, f"JSON-LD hours: {hours}", "jsonld")

        # `url` is the venue's own site; `sameAs` is by definition a link to a
        # *different* identity -- an Instagram or Facebook page. They must not
        # be classified the same way, or a venue's Instagram lands in the
        # website slot and the venue reads as having no website at all.
        node_types = _ld_type_names(node)
        for field_name, u in (("url", node.get("url")), ("sameAs", node.get("sameAs"))):
            # A ContactPage or a logo object has a url. That url is the page,
            # not the venue's site. The organization's own url still counts.
            if field_name == "url" and node_types & _URL_SKIP_TYPES and not (
                node_types & {"organization", "musicvenue", "localbusiness", "place"}
            ):
                continue
            vals = u if isinstance(u, list) else [u]
            for val in vals:
                if not isinstance(val, str) or not val.strip():
                    continue
                val = val.strip()
                host = urllib.parse.urlparse(
                    val if "//" in val else "//" + val).netloc.lower()
                social = next((n for d, n in SOCIAL_DOMAINS.items() if host.endswith(d)), None)
                if field_name == "sameAs" and social:
                    emit(KIND_SOCIAL, val, val, f"JSON-LD sameAs: {val}", "jsonld")
                elif val.startswith(("http://", "https://")):
                    emit(KIND_WEBSITE, val, val, f"JSON-LD {field_name}: {val}", "jsonld")
                elif field_name == "sameAs":
                    emit(KIND_SOCIAL, val, val, f"JSON-LD sameAs: {val}", "jsonld")

    # ---- 2. tel:/mailto: links
    parser = _LinkHarvester()
    try:
        parser.feed(html)
    except Exception:
        pass

    for href in parser.hrefs:
        if href.lower().startswith("tel:"):
            num = href[4:].strip()
            emit(KIND_PHONE, num, num, f'href="{href}"', "tel_link")
        elif href.lower().startswith("mailto:"):
            addr = href[7:].split("?")[0].strip()
            if "@" in addr:
                emit(KIND_EMAIL, addr, addr, f'href="{href}"', "mailto")

        parsed = urllib.parse.urlparse(href if "//" in href else "//" + href)
        host = (parsed.netloc or "").lower()
        if host and host != urllib.parse.urlparse(url).netloc.lower():
            for dom, kind_name in SOCIAL_DOMAINS.items():
                if host.endswith(dom):
                    emit(KIND_SOCIAL, href, href, f'href="{href}"', "social_link")

    # ---- 3. visible text
    text = _strip_tags(html)
    for m in PHONE_RE.finditer(text):
        pretty = f"({m.group(1)}) {m.group(2)}-{m.group(3)}"
        lo = max(0, m.start() - 40)
        emit(KIND_PHONE, pretty, pretty,
             text[lo:m.end() + 40], "text_regex")
    for m in EMAIL_RE.finditer(text):
        emit(KIND_EMAIL, m.group(0), m.group(0),
             text[max(0, m.start() - 30):m.end() + 30], "text_regex")
    for value, excerpt in _find_addresses(text):
        emit(KIND_ADDRESS, value, value, excerpt, "text_regex")

    # Free-form hours, only when the page mentions them and JSON-LD did not.
    if not any(f["kind"] == KIND_HOURS for f in facts):
        for m in HOURS_FREEFORM_RE.finditer(text):
            day, val = m.group("day"), m.group("val").strip()
            if not val or len(val) > 40:
                continue
            if day.lower() not in {"mon", "tue", "wed", "thu", "fri", "sat", "sun",
                                   "monday", "tuesday", "wednesday", "thursday",
                                   "friday", "saturday", "sunday"}:
                continue
            emit(KIND_HOURS, f"{day}: {val}", f"{day}: {val}",
                 m.group(0)[:200], "text_regex")

    return facts


def enrich_venue(
    store,
    entity_id: str,
    url: str,
    *,
    source_id: str | None = None,
    citation_kind: str = "html",
    timeout: int = 30,
) -> dict:
    """Fetch one URL and write every fact it supports onto an entity.

    Returns a summary so a caller can tell "found nothing" apart from "the
    site was down" — the same distinction `venue_dossier.not_found` makes, but
    at the moment of the crawl.
    """
    status, html = _http_get(url, timeout=timeout)
    source_id = source_id or f"web:{urllib.parse.urlparse(url).netloc}"

    if not html:
        return {"url": url, "http_status": status, "facts": 0,
                "written": 0, "error": "no content retrieved"}

    facts = extract_facts(url, html)

    written = 0
    errors: list[str] = []
    for f in facts:
        try:
            add_item(
                store,
                entity_id=entity_id,
                kind=f["kind"],
                value=f["value"],
                display=f["display"],
                source_id=source_id,
                source_url=url,
                citation_kind=citation_kind,
                excerpt=f["excerpt"],
            )
            written += 1
        except Exception as exc:   # noqa: BLE001 - report, don't abort the scan
            errors.append(f"{f['kind']}={f['value']!r}: {exc}")

    return {"url": url, "http_status": status, "facts": len(facts),
            "written": written, "errors": errors,
            "by_method": _count_methods(facts)}


def _count_methods(facts: list[dict]) -> dict:
    out: dict[str, int] = {}
    for f in facts:
        out[f["method"]] = out.get(f["method"], 0) + 1
    return out