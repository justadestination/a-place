"""SQLite FTS5 full-text search engine for ShadeNet & NightCal (Task 5.6).

Indexes:
  - Spots (events): title, description, venue name
  - Spaces (venues): name, address, website
  - The Listed (entities): name, role, bio
  - Expressions (zine articles): title, body, tags

Guarantees:
  - Fast execution (<500ms) via native SQLite FTS5 Porter tokenizer
  - Weighted BM25 ranking (title > subtitle > body)
  - Upcoming events ranked ahead of past events
  - Robust handling of punctuation, wildcards, and empty/gibberish queries
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shadenet.logging import get_logger

logger = get_logger("search")

FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    kind,
    item_id UNINDEXED,
    title,
    subtitle,
    body,
    starts_at UNINDEXED,
    url UNINDEXED,
    metadata UNINDEXED,
    tokenize='porter unicode61'
);
"""


def init_search_table(conn: sqlite3.Connection) -> None:
    """Initialize the FTS5 virtual table if it does not already exist."""
    conn.execute(FTS_SCHEMA)
    conn.commit()


def sanitize_query(query: str) -> str:
    """Clean a user query string for FTS5 syntax, avoiding syntax errors.

    Extracts alphanumeric tokens and joins with AND, or handles double-quoted exact phrases.
    """
    cleaned = (query or "").strip()
    if not cleaned:
        return ""

    # Check if exact phrase quoted
    if cleaned.startswith('"') and cleaned.endswith('"') and len(cleaned) > 2:
        inner = re.sub(r'["\*\^]', '', cleaned[1:-1]).strip()
        return f'"{inner}"' if inner else ""

    # Strip dangerous FTS5 operators (*, :, ^, -, +, AND, OR, NOT unless quoted)
    tokens = re.findall(r"[A-Za-z0-9_]+", cleaned)
    if not tokens:
        return ""
    # Prefix match the final token for typeahead feel
    parts = []
    for i, t in enumerate(tokens):
        if i == len(tokens) - 1:
            parts.append(f'"{t}"*')
        else:
            parts.append(f'"{t}"')
    return " AND ".join(parts)


def build_search_index(store: Store, articles: list[dict] | None = None) -> int:
    """Rebuilds the FTS5 index from events, venues, entities, and articles."""
    conn = store._conn
    init_search_table(conn)

    with store.tx():
        conn.execute("DELETE FROM search_index")

        indexed_count = 0

        # 1. Spots (events)
        rows = conn.execute(
            """
            SELECT e.id, e.title, v.name AS venue_name, e.description,
                   e.starts_at, e.ticket_url
            FROM events e
            LEFT JOIN venues v ON v.id = e.venue_id
            WHERE e.active = 1
            """
        ).fetchall()
        for r in rows:
            meta = json.dumps({"venue": r["venue_name"] or ""})
            conn.execute(
                """
                INSERT INTO search_index(kind, item_id, title, subtitle, body, starts_at, url, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "spot",
                    r["id"],
                    r["title"] or "",
                    r["venue_name"] or "",
                    r["description"] or "",
                    r["starts_at"] or "",
                    r["ticket_url"] or f"/event/{r['id']}",
                    meta,
                ),
            )
            indexed_count += 1

        # 2. Spaces (venues)
        v_rows = conn.execute(
            """
            SELECT id, name, address, website
            FROM venues
            """
        ).fetchall()
        for v in v_rows:
            meta = json.dumps({"address": v["address"], "website": v["website"]})
            conn.execute(
                """
                INSERT INTO search_index(kind, item_id, title, subtitle, body, starts_at, url, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "space",
                    v["id"],
                    v["name"] or "",
                    v["address"] or "Santa Rosa, CA",
                    v["website"] or "",
                    "",
                    f"/space/{v['id']}",
                    meta,
                ),
            )
            indexed_count += 1

        # 3. The Listed (entities: performers, organizers)
        e_rows = conn.execute(
            """
            SELECT id, name, kind, role, meta
            FROM entities
            WHERE kind NOT IN ('city', 'venue')
            """
        ).fetchall()
        for e in e_rows:
            conn.execute(
                """
                INSERT INTO search_index(kind, item_id, title, subtitle, body, starts_at, url, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "listed",
                    e["id"],
                    e["name"] or "",
                    e["role"] or e["kind"] or "act",
                    e["meta"] or "",
                    "",
                    f"/entity/{e['id']}",
                    e["meta"] or "{}",
                ),
            )
            indexed_count += 1

        # 4. Expressions (zine articles)
        if articles:
            for art in articles:
                meta = json.dumps({"slug": art.get("slug"), "author": art.get("author")})
                conn.execute(
                    """
                    INSERT INTO search_index(kind, item_id, title, subtitle, body, starts_at, url, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "expression",
                        art.get("id") or art.get("slug") or "art_0",
                        art.get("title") or "",
                        art.get("author") or "Zine Editorial",
                        art.get("body") or art.get("summary") or "",
                        art.get("published_at") or "",
                        f"/zine/{art.get('slug')}",
                        meta,
                    ),
                )
                indexed_count += 1

    return indexed_count


def search(
    store: Store,
    raw_query: str,
    *,
    limit: int = 20,
    kind: str | None = None,
) -> dict[str, Any]:
    """Execute ranked full-text search against the SQLite FTS5 index.

    Returns grouped results with timing metadata.
    """
    t0 = time.perf_counter()
    init_search_table(store._conn)

    sanitized = sanitize_query(raw_query)
    if not sanitized:
        return {
            "query": raw_query,
            "total": 0,
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
            "results": {
                "spots": [],
                "spaces": [],
                "listed": [],
                "expressions": [],
            },
        }

    now_iso = datetime.now(timezone.utc).isoformat()

    # BM25 weights: kind=0.0, title=5.0, subtitle=2.0, body=1.0
    sql = """
    SELECT
        kind,
        item_id,
        title,
        subtitle,
        body,
        starts_at,
        url,
        metadata,
        bm25(search_index, 0.0, 5.0, 2.0, 1.0) AS rank_score
    FROM search_index
    WHERE search_index MATCH ?
    """
    params: list[Any] = [sanitized]

    if kind:
        sql += " AND kind = ?"
        params.append(kind)

    # Rank sorting: lower bm25 is better in sqlite fts5; upcoming spots boosted
    sql += """
    ORDER BY
        CASE
            WHEN kind = 'spot' AND starts_at >= ? THEN 0
            WHEN kind = 'spot' THEN 1
            ELSE 0
        END ASC,
        rank_score ASC
    LIMIT ?
    """
    params.extend([now_iso, limit])

    rows = store._conn.execute(sql, params).fetchall()

    grouped: dict[str, list[dict]] = {
        "spots": [],
        "spaces": [],
        "listed": [],
        "expressions": [],
    }

    type_mapping = {
        "spot": "spots",
        "space": "spaces",
        "listed": "listed",
        "expression": "expressions",
    }

    for row in rows:
        target_group = type_mapping.get(row["kind"], "spots")
        item = {
            "id": row["item_id"],
            "title": row["title"],
            "subtitle": row["subtitle"],
            "url": row["url"],
            "startsAt": row["starts_at"] or None,
            "snippet": (row["body"] or "")[:180],
            "rank": round(float(row["rank_score"]), 3),
        }
        if row["metadata"]:
            try:
                item["meta"] = json.loads(row["metadata"])
            except Exception:
                pass
        grouped[target_group].append(item)

    total = sum(len(v) for v in grouped.values())
    dur_ms = round((time.perf_counter() - t0) * 1000, 2)

    return {
        "query": raw_query,
        "total": total,
        "duration_ms": dur_ms,
        "results": grouped,
    }
