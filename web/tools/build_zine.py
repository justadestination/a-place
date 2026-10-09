#!/usr/bin/env python3
"""Build web/data/zine.json: the AVR+JIT zine as a graph for the node map.

Reads Obsidian-style markdown notes (YAML-ish frontmatter + body) from the
vault in git, and the calendar model for events and venues. Produces:

    nodes  notes (article / review / letter / editorial), events, venues,
           and "missing" nodes for [[links]] or frontmatter ids that resolve
           to nothing (Obsidian shows these as unresolved; so do we)
    edges  [[wiki-links]] (kind "link"), frontmatter relations
           (kind "events" / "venues"), and event -> venue ("at")

Bodies are rendered to HTML here, at build time, with everything escaped, so
the browser never parses markdown or trusts note text.

    python3 web/tools/build_zine.py [--vault DIR] [--model FILE] [--out FILE]
"""

from __future__ import annotations

import argparse
import email.utils
import html
import json
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent
ROOT = WEB.parent
NOTE_TYPES = {
    "article", "review", "letter", "editorial",
    "stance", "dossier", "dossier-piece", "prediction", "cartoon-brief",
    "topic-overview", "topic-report",
}
NIGHT_KINDS = {"music", "comedy", "show", "trivia"}
WIKI = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "note"


def parse_scalar(raw: str):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [parse_scalar(part) for part in inner.split(",")] if inner else []
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    return raw


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta: dict = {}
    for line in text[3:end].strip().splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            meta[key.strip()] = parse_scalar(value)
    return meta, text[end + 4:].lstrip("\n")


def inline(text: str, link) -> str:
    """Escape, then apply a small, safe inline markdown subset."""
    out = html.escape(text, quote=True)
    out = WIKI.sub(lambda m: link(html.unescape(m.group(1)).strip(), html.unescape(m.group(2) or m.group(1)).strip()), out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![*\w])\*([^*]+)\*(?![*\w])", r"<em>\1</em>", out)
    out = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        lambda m: f'<a href="{m.group(2)}" rel="noopener" target="_blank">{m.group(1)}</a>',
        out,
    )
    return out


def render(body: str, title: str, link) -> str:
    blocks, para, items = [], [], []

    def flush():
        nonlocal para, items
        if para:
            blocks.append(f"<p>{inline(' '.join(para), link)}</p>")
            para = []
        if items:
            blocks.append("<ul>" + "".join(f"<li>{inline(i, link)}</li>" for i in items) + "</ul>")
            items = []

    for line in body.splitlines():
        stripped = line.strip()
        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if not stripped:
            flush()
        elif heading:
            flush()
            level = len(heading.group(1))
            text = heading.group(2).strip()
            if level == 1 and (not blocks) and slugify(text) in slugify(title):
                continue  # the reader already shows the title
            blocks.append(f"<h{min(level + 1, 4)}>{inline(text, link)}</h{min(level + 1, 4)}>")
        elif re.match(r"^[-*]\s+", stripped):
            if para:
                flush()
            items.append(re.sub(r"^[-*]\s+", "", stripped))
        else:
            if items:
                flush()
            para.append(stripped)
    flush()
    return "\n".join(blocks)


def summary_of(body: str) -> str:
    for line in body.splitlines():
        s = line.strip()
        if s and not s.startswith("#") and not s.startswith("-"):
            return WIKI.sub(lambda m: m.group(2) or m.group(1), s)[:200]
    return ""


def load_model(path: Path) -> dict:
    raw = json.loads(path.read_text())
    return raw.get("updateDataModel", {}).get("value", raw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=str(ROOT / "shadenet" / "horizon" / "vault"))
    ap.add_argument("--zine-dir", default=str(ROOT / "zine-automation"))
    ap.add_argument("--model", default=str(WEB / "data" / "sample-model.json"))
    ap.add_argument("--out", default=str(WEB / "data" / "zine.json"))
    args = ap.parse_args()

    model = load_model(Path(args.model))
    venues = {v["id"]: v for v in model.get("venues", [])}
    venues_by_name = {slugify(v["name"]): v["id"] for v in model.get("venues", []) if v.get("name")}
    events = {e["id"]: e for e in model.get("events", []) if not e.get("suppressed")}
    events_by_title = {slugify(e["title"]): e["id"] for e in events.values() if e.get("title")}

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    seen_edges: set[tuple[str, str, str]] = set()

    def edge(a: str, b: str, kind: str):
        key = (min(a, b), max(a, b), kind)
        if a != b and key not in seen_edges:
            seen_edges.add(key)
            edges.append({"source": a, "target": b, "kind": kind})

    def missing(ref: str, hint: str) -> str:
        node_id = f"missing:{slugify(ref)}"
        nodes.setdefault(node_id, {
            "id": node_id, "slug": slugify(ref), "type": "missing", "title": ref,
            "summary": f"Linked from the zine but {hint}.",
        })
        return node_id

    def event_node(eid: str) -> str:
        e = events[eid]
        node_id = f"event:{eid}"
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id, "slug": eid, "type": "event", "title": e["title"], "ref": eid,
                "date": e.get("date", ""), "summary": " · ".join(x for x in (e.get("date", ""), e.get("startLabel", ""), e.get("venue", "")) if x),
                "kind": e.get("kind", "other"),
            }
            if e.get("venueId") in venues:
                edge(node_id, venue_node(e["venueId"]), "at")
        return node_id

    def venue_node(vid: str) -> str:
        v = venues[vid]
        node_id = f"venue:{vid}"
        nodes.setdefault(node_id, {
            "id": node_id, "slug": vid, "type": "venue", "title": v["name"], "ref": vid,
            "summary": v.get("address") or (v.get("amenity") or "").replace("_", " ").title(),
        })
        return node_id

    # Pass 1: notes, so wiki-links can resolve against titles and filenames.
    notes = []
    # 1. Vault notes
    for path in sorted(Path(args.vault).glob("*.md")):
        meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
        title = str(meta.get("title") or path.stem.replace("-", " ").title())
        kind = str(meta.get("type") or "article").lower()
        node_id = f"note:{path.stem}"
        nodes[node_id] = {
            "id": node_id, "slug": path.stem, "type": kind if kind in NOTE_TYPES else "article",
            "title": title, "date": str(meta.get("date") or ""), "author": str(meta.get("author") or ""),
            "status": str(meta.get("status") or ""), "tags": meta.get("tags") or [],
            "summary": summary_of(body),
            "source": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        }
        notes.append((node_id, meta, body))

    # 2. Zine automation published pieces (Hookup 2)
    zine_dir = Path(args.zine_dir)
    pub_dir = zine_dir / "published"
    if pub_dir.exists():
        for path in sorted(pub_dir.glob("*.md")):
            meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
            title = str(meta.get("title") or path.stem.replace("-", " ").title())
            kind = str(meta.get("type") or "article").lower()
            node_id = f"note:{path.stem}"
            nodes[node_id] = {
                "id": node_id, "slug": path.stem, "type": kind if kind in NOTE_TYPES else "article",
                "title": title, "date": str(meta.get("date") or ""), "author": str(meta.get("author") or ""),
                "status": str(meta.get("status") or "published"), "tags": meta.get("tags") or [],
                "stance": meta.get("stance"), "persona": meta.get("persona"),
                "summary": summary_of(body),
                "source": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            }
            notes.append((node_id, meta, body))

    # 3. Zine automation topics (Hookup 3)
    topics_dir = zine_dir / "topics"
    if topics_dir.exists():
        for topic_path in sorted(topics_dir.glob("*")):
            if not topic_path.is_dir() or topic_path.name.startswith("_"):
                continue
            tslug = topic_path.name
            overview_file = topic_path / "overview.md"
            report_file = topic_path / "full-report.md"
            if overview_file.exists():
                meta_ov, body_ov = split_frontmatter(overview_file.read_text(encoding="utf-8"))
                if meta_ov.get("status") == "published":
                    ov_id = f"note:topic-{tslug}"
                    nodes[ov_id] = {
                        "id": ov_id, "slug": tslug, "type": "topic-overview",
                        "title": str(meta_ov.get("title") or f"{tslug.replace('-', ' ').title()} Overview"),
                        "date": str(meta_ov.get("date") or ""), "author": "Umwelt Horizons Research Desk",
                        "status": "published", "tags": ["topic", "dossier"],
                        "summary": summary_of(body_ov),
                        "source": str(overview_file.relative_to(ROOT)) if overview_file.is_relative_to(ROOT) else str(overview_file),
                    }
                    notes.append((ov_id, meta_ov, body_ov))
            if report_file.exists():
                meta_rep, body_rep = split_frontmatter(report_file.read_text(encoding="utf-8"))
                if meta_rep.get("status") == "published":
                    rep_id = f"note:topic-{tslug}-report"
                    nodes[rep_id] = {
                        "id": rep_id, "slug": f"{tslug}-report", "type": "topic-report",
                        "title": str(meta_rep.get("title") or f"{tslug.replace('-', ' ').title()} Full Report"),
                        "date": str(meta_rep.get("date") or ""), "author": "Umwelt Horizons Research Desk",
                        "status": "published", "tags": ["topic", "report"],
                        "summary": summary_of(body_rep),
                        "source": str(report_file.relative_to(ROOT)) if report_file.is_relative_to(ROOT) else str(report_file),
                    }
                    notes.append((rep_id, meta_rep, body_rep))

    by_name = {}
    for node_id, meta, _ in notes:
        n = nodes[node_id]
        by_name[slugify(n["slug"])] = node_id
        by_name[slugify(n["title"])] = node_id

    # Pass 2: bodies and relations.
    for node_id, meta, body in notes:
        def link(target: str, text: str, _from=node_id) -> str:
            ref = by_name.get(slugify(target))
            if not ref and target in events:
                ref = event_node(target)
            if not ref and slugify(target) in events_by_title:
                ref = event_node(events_by_title[slugify(target)])
            if not ref and target in venues:
                ref = venue_node(target)
            if not ref and slugify(target) in venues_by_name:
                ref = venue_node(venues_by_name[slugify(target)])
            if not ref:
                ref = missing(target, "nothing with that name exists yet")
            edge(_from, ref, "link")
            cls = ' class="is-missing"' if ref.startswith("missing:") else ""
            return f'<a href="?node={html.escape(ref)}" data-node="{html.escape(ref)}"{cls}>{html.escape(text)}</a>'

        nodes[node_id]["html"] = render(body, nodes[node_id]["title"], link)
        for eid in meta.get("events") or []:
            edge(node_id, event_node(eid) if eid in events else missing(str(eid), "that event is not in the calendar"), "events")
        for vid in meta.get("venues") or []:
            edge(node_id, venue_node(vid) if vid in venues else missing(str(vid), "that venue is not in the calendar"), "venues")

        # Wire topic relation edges
        if meta.get("topic"):
            tslug = slugify(str(meta.get("topic")))
            t_ref = by_name.get(tslug) or by_name.get(f"topic-{tslug}")
            if t_ref:
                edge(node_id, t_ref, "topic")
        if node_id.startswith("note:topic-") and not node_id.endswith("-report"):
            rep_id = f"{node_id}-report"
            if rep_id in nodes:
                edge(node_id, rep_id, "report")

    # Calendar context: every night-out event and the room it is in.
    for eid, e in events.items():
        if e.get("kind") in NIGHT_KINDS:
            event_node(eid)

    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "vault": str(Path(args.vault).resolve().relative_to(ROOT)) if Path(args.vault).resolve().is_relative_to(ROOT) else args.vault,
        "nodes": sorted(nodes.values(), key=lambda n: (n["type"] not in NOTE_TYPES, n["type"], n["title"].lower())),
        "edges": edges,
    }
    # Keep the old timestamp when nothing else changed, so rebuilds don't churn git.
    target = Path(args.out)
    if target.exists():
        try:
            prev = json.loads(target.read_text())
            if {k: v for k, v in prev.items() if k != "generatedAt"} == {k: v for k, v in out.items() if k != "generatedAt"}:
                out["generatedAt"] = prev.get("generatedAt", out["generatedAt"])
        except json.JSONDecodeError:
            pass
    target.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    counts = {}
    for n in out["nodes"]:
        counts[n["type"]] = counts.get(n["type"], 0) + 1
    print(f"zine: {len(out['nodes'])} nodes {counts}, {len(edges)} edges -> {args.out}")

    # Generate full-content RSS 2.0 feed (Task 3.4)
    rss_xml = generate_rss_feed(out["nodes"])
    rss_path = WEB / "zine" / "feed.xml"
    rss_path.parent.mkdir(parents=True, exist_ok=True)
    rss_path.write_text(rss_xml, encoding="utf-8")
    (WEB / "feed.xml").write_text(rss_xml, encoding="utf-8")
    print(f"rss: generated full-content feed ({rss_path})")
    return 0


def generate_rss_feed(nodes: list[dict], site_url: str = "https://nightcal.example.org") -> str:
    now_dt = datetime.now(timezone.utc)
    pub_date_now = email.utils.format_datetime(now_dt)

    items_xml = []
    for n in sorted(nodes, key=lambda x: str(x.get("date") or "9999"), reverse=True):
        if n.get("type") not in NOTE_TYPES or not n.get("html"):
            continue
        title = html.escape(str(n.get("title") or "Untitled Dispatch"))
        node_id = str(n.get("id") or "")
        item_link = f"{site_url}/zine/?node={urllib.parse.quote(node_id)}"

        item_date = pub_date_now
        if n.get("date"):
            try:
                d = datetime.fromisoformat(str(n["date"])).replace(tzinfo=timezone.utc)
                item_date = email.utils.format_datetime(d)
            except Exception:
                pass

        author = html.escape(str(n.get("author") or "Umwelt Horizons Contributor"))
        summary = html.escape(str(n.get("summary") or ""))
        content_encoded = str(n.get("html") or "")

        items_xml.append(f"""    <item>
      <title>{title}</title>
      <link>{item_link}</link>
      <guid isPermaLink="false">{html.escape(node_id)}</guid>
      <pubDate>{item_date}</pubDate>
      <author>noreply@example.org ({author})</author>
      <description>{summary}</description>
      <content:encoded><![CDATA[{content_encoded}]]></content:encoded>
    </item>""")

    feed_items = "\n".join(items_xml)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Umwelt Horizons · NightCal Zine</title>
    <link>{site_url}/zine/</link>
    <description>Dispatches, reviews, and underground dispatches from the Santa Rosa nightlife graph.</description>
    <language>en-us</language>
    <lastBuildDate>{pub_date_now}</lastBuildDate>
    <atom:link href="{site_url}/zine/feed.xml" rel="self" type="application/rss+xml"/>
{feed_items}
  </channel>
</rss>
"""


if __name__ == "__main__":
    raise SystemExit(main())
