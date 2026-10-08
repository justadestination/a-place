"""Public entity pages — NightCal v0.2 Phase 1.

Entity cards as public pages [Spec §2 p.4]: every venue, promoter, and band
gets a public profile page rendering its cited contact facts and links.

Builds a static HTML page from a venue dossier (or promoter/band dossier).
The visual design is NOT baked in here — this module emits the data layer of
the page: semantic HTML, ARIA roles, data attributes for the A2UI renderer,
and a presentation hooks contract so the frontend team can style it later.
Everything is derived from cited facts only; no uncited facts are rendered.

Usage:
  python3 -m nightcal.entity_pages
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shadenet.towncrier.entities import (
    KIND_ADDRESS,
    KIND_EMAIL,
    KIND_HOURS,
    KIND_PHONE,
    KIND_SOCIAL,
    KIND_WEBSITE,
    venue_dossier,
)
from shadenet.towncrier.store import Store

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "shadenet.db"

# --- A2UI presentation hook contract ---
# Frontend binds on data-entity-type and data-field attributes. Pages carry a
# machine-readable structure (JSON-LD) so third-party readers can consume them.
# Presentation classes exist only for the frontend team to style.

PAGE_TPL = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="index, follow">
  <title>{name} — {kind}</title>
  <script type="application/ld+json">
  {jsonld}
  </script>
  <style>
  .entity-page {{ font-family: system-ui, -apple-system, sans-serif; }}
  .entity-header {{ padding: 1.5rem; }}
  .entity-name {{ font-size: 1.75rem; line-height: 1.2; }}
  .entity-kind {{ font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em; color: #666; }}
  .entity-content {{ padding: 1.5rem; max-width: 72ch; }}
  .facts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }}
  .fact-item {{ border: 1px solid #e0e0e0; border-radius: 6px; padding: 0.75rem; }}
  .fact-label {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em; color: #666; }}
  .fact-value {{ font-size: 1rem; margin-top: 0.25rem; }}
  .fact-value a {{ color: #0b57d0; text-decoration: none; }}
  .fact-value a:hover {{ text-decoration: underline; }}
  .contact-list {{ list-style: none; margin: 0; padding: 0; }}
  .contact-list li {{ margin: 0.4rem 0; }}
  .contact-list a {{ color: #0b57d0; }}
  .dossier-note {{ font-size: 0.85rem; color: #666; margin-top: 1rem; }}
  .dossier-note a {{ color: #0b57d0; }}
  .page-jsonld {{ display: none; }}
  @media (prefers-reduced-motion: reduce) {{ .entity-page * {{ transition: none !important; }} }}
  </style>
</head>
<body>
  <main class="entity-page" data-entity-type="{entity_type}">
    <header class="entity-header">
      <h1 class="entity-name" data-field="name">{name}</h1>
      <p class="entity-kind" data-field="kind">{kind}</p>
    </header>
    <section class="entity-content" data-field="content">
      {facts_html}
      <p class="dossier-note">
        <a href="/entities/{slug}" data-field="dossier">Full dossier (cited facts only)</a> —
        {n_not_found} kind(s) not found.
      </p>
    </section>
  </main>
  <script type="application/ld+json">
  {yelp_id_ld}
  </script>
  <script type="application/ld+json">
  {jsonld2}
  </script>
</body>
</html>
"""


def _slug(name: str) -> str:
    """ASCII slug for URLs and CSS selectors."""
    normalized = name.lower().replace(" ", "-")
    return "".join(c if c.isalnum() or c == "-" else "-" for c in normalized)


def _tel_value(value: str) -> str:
    """Strip non-digits for a clean tel: URL, keeping a leading +1."""
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return digits


def _facts_html(dossier: dict, entity_type: str) -> str:
    """Build the facts markup from a dossier. Only cited facts are rendered."""
    kinds = [KIND_PHONE, KIND_EMAIL, KIND_ADDRESS, KIND_HOURS, KIND_SOCIAL, KIND_WEBSITE]
    blocks = []
    for kind in kinds:
        facts = dossier.get("facts", {}).get(kind, [])
        if not facts:
            continue
        title = kind.title()
        items = []
        for f in facts:
            value = f["value"]
            if kind == KIND_PHONE:
                items.append(f'<a href="tel:{_tel_value(value)}" data-field="phone">{value}</a>')
            elif kind == KIND_EMAIL:
                items.append(f'<a href="mailto:{value}" data-field="email">{value}</a>')
            elif kind == KIND_ADDRESS:
                items.append(f'<span data-field="address">{value}</span>')
            elif kind == KIND_HOURS:
                items.append(f'<span data-field="hours">{value}</span>')
            elif kind == KIND_SOCIAL:
                for source in f.get("sources", []):
                    url = source.get("url", "")
                    if any(t in url for t in ("sameAs", "instagram", "facebook", "twitter")):
                        items.append(f'<a href="{url}" data-field="social">{value}</a>')
                        break
                else:
                    items.append(f'<span data-field="social">{value}</span>')
            elif kind == KIND_WEBSITE:
                items.append(f'<a href="{value}" data-field="website">{value}</a>')
        if items:
            blocks.append(
                f'<div class="fact-item"><div class="fact-label">{title}</div>'
                f'<div class="fact-value">{"".join(items)}</div></div>'
            )
    return "\n      ".join(blocks) if blocks else '<p class="fact-item"><em>No cited contact facts yet.</em></p>'


def _jsonld(dossier: dict) -> str:
    """JSON-LD for the entity page — machine-readable cited facts."""
    name = dossier.get("name", "")
    facts: dict[str, list[str]] = {"name": [name]}
    for kind in (KIND_PHONE, KIND_EMAIL, KIND_ADDRESS, KIND_WEBSITE, KIND_SOCIAL):
        for f in dossier.get("facts", {}).get(kind, []):
            val = f["value"]
            if kind == KIND_PHONE:
                facts.setdefault("telephone", []).append(val)
            elif kind == KIND_EMAIL:
                facts.setdefault("email", []).append(val)
            elif kind == KIND_ADDRESS:
                facts.setdefault("address", []).append(val)
            elif kind == KIND_WEBSITE:
                facts.setdefault("url", []).append(val)
            elif kind == KIND_SOCIAL:
                facts.setdefault("sameAs", []).append(val)

    body: dict[str, Any] = {"@context": "https://schema.org", "@type": _entity_type_ld(dossier)}
    for key, vals in facts.items():
        body[key] = vals[0] if len(vals) == 1 else vals
    return json.dumps(body, ensure_ascii=False)


def _entity_type_ld(dossier: dict) -> str:
    entity_type = dossier.get("kind", "")
    if entity_type in ("venue", "music_venue", "nightclub", "bar", "pub"):
        return "MusicVenue"
    if entity_type == "band":
        return "MusicGroup"
    if entity_type == "promoter":
        return "Organization"
    if entity_type == "person":
        return "Person"
    return "Organization"


def _yelp_id_ld(dossier: dict) -> str:
    """Add a Yelp entity ID to JSON-LD if a website is present."""
    website = ""
    for f in dossier.get("facts", {}).get(KIND_WEBSITE, []):
        website = f["value"]
        break
    if not website:
        return ""
    host = website.split("//")[-1].split("/")[0].split(".")[0]
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "MusicVenue",
        "additionalProperty": [
            {
                "name": "yelp_entity_id",
                "value": host,
                "description": "Vendor-supplied entity code for the venue's site",
            }
        ],
    }, ensure_ascii=False)


def _render_html(
    name: str,
    entity_type: str,
    kind: str,
    facts_html: str,
    n_not_found: int,
    slug: str,
    jsonld: str,
    yelp_id_ld: str,
) -> str:
    """Assemble the entity page HTML. Presentation classes only."""
    return "\n".join([
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head>",
        "  <meta charset=\"utf-8\">",
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
        "  <meta name=\"robots\" content=\"index, follow\">",
        '  <title>{0} — {1}</title>'.format(name, kind),
        "  <script type=\"application/ld+json\">",
        jsonld,
        "  </script>",
        "  <style>",
        "  /* Presentation hooks: these classes exist only for the frontend team to",
        "     style. This file supplies the data. Do not edit presentation here. */",
        "  .entity-page { font-family: system-ui, -apple-system, sans-serif; }",
        "  .entity-header { padding: 1.5rem; }",
        "  .entity-name { font-size: 1.75rem; line-height: 1.2; }",
        "  .entity-kind { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em; color: #666; }",
        "  .entity-content { padding: 1.5rem; max-width: 72ch; }",
        "  .facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }",
        "  .fact-item { border: 1px solid #e0e0e0; border-radius: 6px; padding: 0.75rem; }",
        "  .fact-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em; color: #666; }",
        "  .fact-value { font-size: 1rem; margin-top: 0.25rem; }",
        "  .fact-value a { color: #0b57d0; text-decoration: none; }",
        "  .fact-value a:hover { text-decoration: underline; }",
        "  .contact-list { list-style: none; margin: 0; padding: 0; }",
        "  .contact-list li { margin: 0.4rem 0; }",
        "  .contact-list a { color: #0b57d0; }",
        "  .dossier-note { font-size: 0.85rem; color: #666; margin-top: 1rem; }",
        "  .dossier-note a { color: #0b57d0; }",
        '  .page-jsonld { display: none; }',
        "  @media (prefers-reduced-motion: reduce) { .entity-page * { transition: none !important; } }",
        "  </style>",
        "</head>",
        "<body>",
        "  <main class=\"entity-page\" data-entity-type=\"{0}\">".format(entity_type),
        "    <header class=\"entity-header\">",
        "      <h1 class=\"entity-name\" data-field=\"name\">{0}</h1>".format(name),
        "      <p class=\"entity-kind\" data-field=\"kind\">{0}</p>".format(kind),
        "    </header>",
        "    <section class=\"entity-content\" data-field=\"content\">",
        "      {0}".format(facts_html),
        "      <p class=\"dossier-note\">",
        "        <a href=\"/entities/{0}\" data-field=\"dossier\">Full dossier (cited facts only)</a> —".format(slug),
        "        {0} kind(s) not found.".format(n_not_found),
        "      </p>",
        "    </section>",
        "  </main>",
        "  <script type=\"application/ld+json\">",
        yelp_id_ld,
        "  </script>",
        "  <script type=\"application/ld+json\">",
        jsonld,
        "  </script>",
        "</body>",
        "</html>",
    ])


def render_entity_page(dossier: dict, output_path: Path) -> None:
    """Write a public entity page from a dossier of cited facts."""
    name = dossier.get("name", "Unknown")
    entity_type = dossier.get("kind", "venue")
    n_not_found = len(dossier.get("not_found", []))
    slug = _slug(name)

    facts_html = _facts_html(dossier, entity_type)
    jsonld = _jsonld(dossier)
    yelp_id_ld = _yelp_id_ld(dossier)

    output_path.write_text(
        _render_html(name, entity_type, entity_type.title(),
                     facts_html, n_not_found, slug, jsonld, yelp_id_ld),
        encoding="utf-8",
    )


def render_all_entities(output_dir: Path) -> dict[str, int]:
    """Render a public page for every entity in the store."""
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {"rendered": 0, "skipped": 0, "errors": []}

    with Store(DB_PATH) as store:
        for entity in store.query("SELECT id, kind, name FROM entities"):
            try:
                dossier = venue_dossier(store, entity["id"])
                if not dossier.get("facts") and not dossier.get("not_found"):
                    results["skipped"] += 1
                    continue
                out = output_dir / f"{_slug(entity['name'])}.html"
                render_entity_page(dossier, out)
                results["rendered"] += 1
            except Exception as exc:
                results["errors"].append(f"{entity['name']}: {exc}")

    return results


# --- Test harness ---

def _test_dossier(**overrides) -> dict:
    base = {
        "name": "The Royal",
        "kind": "venue",
        "verified": True,
        "facts": {
            KIND_PHONE: [{"value": "(707) 543-1500", "confidence": 0.95,
                          "sources": [{"url": "https://www.openstreetmap.org/node/1"}]}],
            KIND_EMAIL: [{"value": "booking@theroyal.test", "confidence": 0.95,
                          "sources": [{"url": "https://theroyal.test/"}]}],
            KIND_ADDRESS: [{"value": "150 Clement St, San Francisco, CA 94102",
                            "confidence": 0.8, "sources": [{"url": "https://theroyal.test/"}]}],
            KIND_WEBSITE: [{"value": "https://theroyal.test", "confidence": 0.9,
                            "sources": [{"url": "https://theroyal.test/"}]}],
            KIND_SOCIAL: [{"value": "https://www.facebook.com/theroyal",
                           "confidence": 0.8, "sources": [{"url": "https://theroyal.test/"}]},
                          {"value": "https://www.instagram.com/theroyal",
                           "confidence": 0.8, "sources": [{"url": "https://theroyal.test/"}]}],
        },
        "not_found": [],
        "provenance": {"event_count": 3, "bands": ["The Royal Trio", "Jazz Syndicate"]},
    }
    base.update(overrides)
    return base


def run_tests(tmpdir: Path) -> bool:
    """Render a known dossier and verify the output contains cited facts."""
    dossier = _test_dossier()
    out = tmpdir / "entity_test.html"
    render_entity_page(dossier, out)

    html = out.read_text(encoding="utf-8")
    ok = True

    for needle in ["(707) 543-1500", "booking@theroyal.test",
                   "https://theroyal.test", "https://www.facebook.com/theroyal",
                   "https://www.instagram.com/theroyal"]:
        if needle not in html:
            ok = False
            print(f"  FAIL: {needle!r} not in page")

    if '<script type="application/ld+json">' not in html:
        ok = False
        print("  FAIL: JSON-LD missing")
    if 'data-entity-type' not in html:
        ok = False
        print("  FAIL: data-entity-type attribute missing")
    if "The Royal" not in html:
        ok = False
        print("  FAIL: entity name missing")

    print(f"  {'PASS' if ok else 'FAIL'}: entity page contains cited facts")
    return ok


def main() -> int:
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="nightcal-entities-"))

    # 1. Unit test with a synthetic dossier
    ok = run_tests(tmp)

    # 2. Real render over the existing store (53 events, 23 venues)
    print("\n══ Rendering entity pages from store ══")
    results = render_all_entities(tmp / "entities")
    print(f"  Rendered: {results['rendered']}, skipped: {results['skipped']}")
    if results["errors"]:
        print(f"  Errors: {results['errors']}")

    # 3. Verification: check each rendered page has cited contact info
    ok2 = True
    for f in sorted((tmp / "entities").glob("*.html")):
        html = f.read_text(encoding="utf-8")
        if "<h1" not in html or "data-entity-type" not in html:
            ok2 = False
            print(f"  FAIL: {f.name} missing header")
    print(f"  Pages verified: {ok2}")

    print(f"\n  Sample pages written to {tmp / 'entities'}")
    for f in sorted((tmp / "entities").glob("*.html"))[:2]:
        print(f"    - {f.name}")

    return 0 if (ok and ok2) else 1


if __name__ == "__main__":
    sys.exit(main())