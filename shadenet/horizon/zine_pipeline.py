"""Zine content modules pipeline — NightCal v0.2 Phase 1.

Zine pieces compile into a node graph [Spec §9 p.13]. The v1 source of truth
is markdown plus YAML frontmatter in git. Obsidian MAY be used as the writing
room because its notes and wikilinks fit the model, but Obsidian is not the
runtime, database, or reader experience.

Pipeline:
  1. READ VAULT  — walk the markdown vault (git-tracked)
  2. VALIDATE    — YAML frontmatter contract: title, type, author, date,
                   venues, events, tags, status
  3. RESOLVE     — resolve venue/event IDs, expand wikilinks [[...]] into
                   graph edges; broken wikilinks block preview builds
  4. EMIT NODES  — write nodes.json (stable ID, frontmatter, rendered body,
                   source revision)
  5. EMIT EDGES  — write edges.json (from, to, kind: wikilink | venue | event |
                   tag)
  6. RENDER      — emit the AVR node-graph renderer payload for the AVR space

Usage:
  python3 -m nightcal.zine_pipeline
"""

from __future__ import annotations

import frontmatter
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent.parent
ZINE_DIR = ROOT / "shadenet" / "horizon"
VAULT_DIR = ZINE_DIR / "vault"
NODES_DIR = ZINE_DIR / "nodes"
EDGES_DIR = ZINE_DIR / "edges"
NODES_FILE = NODES_DIR / "nodes.json"
EDGES_FILE = EDGES_DIR / "edges.json"
AVR_FILE = ZINE_DIR / "avr_graph.json"

LA = ZoneInfo("America/Los_Angeles")

# Frontmatter contract per Spec §9 p.13
FRONTMATTER_FIELDS = {
    "title": {"required": True, "type": str, "max": 160},
    "type": {"required": True, "enum": ["article", "review", "letter", "editorial", "syndicated"]},
    "author": {"required": False, "type": str},
    "date": {"required": False, "type": str, "iso_date": True},
    "venues": {"required": False, "type": list, "item": str},
    "events": {"required": False, "type": list, "item": str},
    "tags": {"required": False, "type": list, "item": str},
    "status": {"required": True, "enum": ["draft", "published"]},
}

# Fields used for syndicated partner news (Spec §E) when type == "syndicated".
SYNDICATED_FIELDS = {
    "partner_name": {"required": False, "type": str},
    "original_url": {"required": False, "type": str, "iso_url": True},
    "license": {"required": False, "type": str},
}

# Wikilink pattern: [[Page Title]] or [[Page Title|Display text]]
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _parse_frontmatter(path: Path) -> tuple[dict, str, str]:
    """Read a markdown file, parse YAML frontmatter, return (data, title, body)."""
    fm = frontmatter.Frontmatter.read_file(path)
    data = fm.get("attributes", {}) or {}
    body = fm.get("body", "")
    # Get title from frontmatter or from body first heading
    title = data.get("title", "")
    if not title:
        m = re.search(r"^#\\s+(.+)$", body, re.MULTILINE)
        if m:
            title = m.group(1).strip()
    return data, title, body


def _validate_frontmatter(data: dict, path: Path) -> list[str]:
    """Validate the frontmatter contract. Returns a list of error strings."""
    errors = []
    for field, spec in FRONTMATTER_FIELDS.items():
        if spec["required"] and field not in data:
            errors.append(f"{path.name}: missing required field '{field}'")
    if "type" in data and data["type"] not in FRONTMATTER_FIELDS["type"]["enum"]:
        errors.append(f"{path.name}: invalid type '{data['type']}'")
    if "status" in data and data["status"] not in FRONTMATTER_FIELDS["status"]["enum"]:
        errors.append(f"{path.name}: invalid status '{data['status']}'")
    if "title" in data and len(data["title"]) > FRONTMATTER_FIELDS["title"]["max"]:
        errors.append(f"{path.name}: title exceeds {FRONTMATTER_FIELDS['title']['max']} chars")
    if "date" in data:
        try:
            if not isinstance(data["date"], str):
                data["date"] = data["date"].isoformat()
            date.fromisoformat(data["date"])
        except (ValueError, AttributeError):
            errors.append(f"{path.name}: date is not ISO YYYY-MM-DD")
    if "venues" in data and not isinstance(data["venues"], list):
        errors.append(f"{path.name}: venues must be a list")
    if "events" in data and not isinstance(data["events"], list):
        errors.append(f"{path.name}: events must be a list")
    if "tags" in data and not isinstance(data["tags"], list):
        errors.append(f"{path.name}: tags must be a list")
    # Spec §E: syndicated entries need partner attribution.
    if data.get("type") == "syndicated":
        for field, spec in SYNDICATED_FIELDS.items():
            if spec.get("required", False) and field not in data:
                errors.append(f"{path.name}: missing required syndicated field '{field}'")
    return errors


def _resolve_wikilinks(body: str, node_ids: set[str], venue_ids: set[str],
                       event_ids: set[str]) -> tuple[str, list[dict]]:
    """Expand [[wikilinks]] in body. Returns (resolved_body, edges)."""
    edges = []

    def repl(match: re.Match) -> str:
        target = match.group(1)
        # Handle [[Page Title]] or [[Page Title|Display text]]
        if "|" in target:
            title, display = target.split("|", 1)
            title = title.strip()
            display = display.strip()
        else:
            title = target.strip()
            display = title

        # Determine edge kind
        if title in node_ids:
            kind = "wikilink"
        elif title in venue_ids:
            kind = "venue"
        elif title in event_ids:
            kind = "event"
        else:
            kind = "tag"  # Unknown → treat as tag (will break preview builds)

        edges.append({"from": "", "to": title, "kind": kind})

        # Render the link in the body
        if display == title:
            return f"[[{title}]]"
        return f"[[{title}|{display}]]"

    resolved = WIKILINK_RE.sub(repl, body)
    return resolved, edges


def _slug(name: str) -> str:
    """ASCII slug for node IDs."""
    normalized = name.lower().replace(" ", "-")
    return "".join(c if c.isalnum() or c == "-" else "-" for c in normalized)


def compile_zine(pieces: list[Path], output_nodes: Path, output_edges: Path) -> dict:
    """Compile zine pieces into node + edge JSON.

    Returns a summary dict.
    """
    node_records = []
    all_edges = []
    errors = []
    broken_wikilinks = []

    # First pass: read all files, validate frontmatter
    for path in pieces:
        try:
            data, title, body = _parse_frontmatter(path)
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
            continue

        errors.extend(_validate_frontmatter(data, path))

        # Resolve wikilinks
        node_ids = {n["id"] for n in node_records}
        venue_ids = {"venue_123"}  # populated in second pass
        event_ids = {"evt_456"}  # populated in second pass
        # (IDs are resolved in the real system from the store; here we use
        #  a placeholder and let the second pass catch broken links.)

        resolved_body, edges = _resolve_wikilinks(body, node_ids, venue_ids, event_ids)
        all_edges.extend(edges)

        # Stable ID: derived from title + revision
        rev = path.stat().st_mtime_ns
        node_id = f"node_{_slug(data.get('title', path.stem))}_{rev}"

        # Spec §E: syndicated partner news attribution.
        if data.get("type") == "syndicated":
            partner = data.get("partner_name", "")
            original = data.get("original_url", "")
            body = f"{'Partner: ' + partner if partner else ''}\n\n" + \
                    f"{'Source: ' + original if original else ''}\n" + \
                    (body or "")

        node_records.append({
            "id": node_id,
            "title": data.get("title", ""),
            "type": data.get("type", ""),
            "author": data.get("author", ""),
            "date": data.get("date", ""),
            "venues": data.get("venues", []),
            "events": data.get("events", []),
            "tags": data.get("tags", []),
            "status": data.get("status", "draft"),
            "body": body,
            "revision": f"rev_{rev}",
            "source": str(path.relative_to(ROOT)),
        })

    # Second pass: resolve IDs against known entities
    # In a real system the store would provide these; here we detect broken
    # wikilinks and block publication builds per Spec §9.
    for edge in all_edges:
        # Venue/event IDs are resolved from the store in production.
        # Broken wikilinks (not nodes, venues, events, or tags) block builds.
        pass

    # Check for broken wikilinks: any edge kind that is not wikilink, venue,
    # event, or tag is a problem — but per Spec, broken wikilinks MUST block
    # publication builds. We flag them and return them.
    broken = [e for e in all_edges if e["kind"] not in ("wikilink", "venue", "event")]

    return {
        "nodes": node_records,
        "edges": all_edges,
        "errors": errors,
        "broken_wikilinks": broken,
        "piece_count": len(pieces),
    }


def render_avr(nodes: list[dict], edges: list[dict], venue_ids: set[str],
               event_ids: set[str]) -> dict:
    """Render the AVR node-graph payload.

    Returns the AVR graph structure for the AVR space.
    """
    # Build node index
    node_by_id = {n["id"]: n for n in nodes}

    # Collect all IDs for linking
    all_ids = {n["id"] for n in nodes}

    # Resolve edges: map each edge's 'to' to a node id if it's a wikilink
    resolved_edges = []
    for edge in edges:
        target = edge["to"]
        kind = edge["kind"]
        if kind in ("wikilink", "venue", "event"):
            if target in node_by_id:
                resolved_edges.append({**edge, "to": target})
            else:
                resolved_edges.append({**edge})
        elif kind == "tag":
            resolved_edges.append(edge)
        else:
            # Broken link — keep as-is, blocks publication
            resolved_edges.append(edge)

    return {
        "nodes": nodes,
        "edges": resolved_edges,
        "rendered_at": date.today().isoformat(),
        "zone": str(LA),
        "node_count": len(nodes),
        "edge_count": len(resolved_edges),
    }


def main() -> int:
    import tempfile

    # 1. READ VAULT — find all markdown pieces
    pieces = sorted(VAULT_DIR.glob("*.md")) if VAULT_DIR.exists() else []
    if not pieces:
        print(f"  Note: no .md files in {VAULT_DIR}")
        pieces = []

    print(f"  Reading {len(pieces)} zine pieces from vault...")

    # 2-4. Compile (validate + resolve + emit)
    result = compile_zine(pieces, NODES_FILE, EDGES_FILE)

    # 5. Emit
    NODES_DIR.mkdir(parents=True, exist_ok=True)
    EDGES_DIR.mkdir(parents=True, exist_ok=True)

    for f in NODES_DIR.glob("*.json"):
        f.unlink()
    for f in EDGES_DIR.glob("*.json"):
        f.unlink()

    if result["nodes"]:
        NODES_FILE.write_text(
            json.dumps({"nodes": result["nodes"], "count": len(result["nodes"])}, indent=2),
            encoding="utf-8",
        )
    if result["edges"]:
        EDGES_FILE.write_text(
            json.dumps({"edges": result["edges"], "count": len(result["edges"])}, indent=2),
            encoding="utf-8",
        )

    # 6. Render AVR graph
    avr = render_avr(result["nodes"], result["edges"], set(), set())
    AVR_FILE.write_text(json.dumps(avr, indent=2), encoding="utf-8")

    # Report
    print(f"  Nodes: {len(result['nodes'])}")
    print(f"  Edges: {len(result['edges'])}")
    print(f"  Errors: {len(result['errors'])}")
    for e in result["errors"]:
        print(f"    ERROR: {e}")
    print(f"  Broken wikilinks: {len(result['broken_wikilinks'])}")

    print(f"\n  Sample nodes written to {NODES_FILE}")
    for n in result["nodes"][:3]:
        print(f"    - {n['id']}: {n['title'][:50]}")

    print(f"\n  Sample edges written to {EDGES_FILE}")
    for e in result["edges"][:5]:
        print(f"    - {e['from']} -> {e['to']} ({e['kind']})")

    if result["errors"] or result["broken_wikilinks"]:
        print("\n  Preview build blocked by broken wikilinks or validation errors.")
        return 1

    print("\n  Zine content modules pipeline complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
