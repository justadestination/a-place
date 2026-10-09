"""Attendance tally backend for NightCal per Phase 0.4 rules.

Rules (Decision 004):
- The +/− tally is strictly a gauge of intended attendance.
  '+' = planning or considering attending; '−' = explicitly not interested.
- Only Stewards cast votes with explicit user approval.
- One human = one Steward identity; 1 vote per steward per event.
- Idempotent: toggling between + and − or retracting updates the single record.
- Rapid toggling collapses to the latest state.
- Unverified visitors cannot affect verified attendance tallies.
"""

from __future__ import annotations

import time
from typing import Any
from shadenet.towncrier.store import Store


def ensure_votes(store: Store) -> None:
    """Ensure both legacy votes table and new tallies table exist."""
    store.execute(
        """
        CREATE TABLE IF NOT EXISTS nightcal_votes (
            listing_url TEXT PRIMARY KEY,
            ups INTEGER NOT NULL DEFAULT 0,
            downs INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    store.execute(
        """
        CREATE TABLE IF NOT EXISTS nightcal_tallies (
            event_id TEXT NOT NULL,
            steward_id TEXT NOT NULL,
            direction TEXT NOT NULL,
            verified INTEGER NOT NULL DEFAULT 1,
            updated_at REAL NOT NULL,
            PRIMARY KEY (event_id, steward_id)
        )
        """
    )
    store.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_nightcal_tallies_event
        ON nightcal_tallies(event_id, verified)
        """
    )


def normalize_direction(direction: str) -> str | None:
    """Normalize direction string to '+' or '−' (or 'retract')."""
    d = str(direction).strip().lower()
    if d in ("+", "up", "pos", "positive", "yes", "in"):
        return "+"
    if d in ("-", "−", "down", "neg", "negative", "no", "out"):
        return "−"
    if d in ("0", "retract", "cancel", "clear", "neutral", "none"):
        return "retract"
    return None


def record_vote(
    store: Store,
    event_id: str,
    direction: str,
    *,
    steward_id: str | None = None,
    verified: bool = True,
    now: float | None = None,
) -> dict[str, Any]:
    """Cast or update an attendance tally vote.

    If steward_id is provided, records per-steward tally with dedup and collapse.
    If steward_id is not provided, defaults to legacy URL-based counter for compatibility.
    """
    ensure_votes(store)
    norm = normalize_direction(direction)
    if norm is None:
        return {"ok": False, "error": f"invalid direction: {direction}"}

    timestamp = time.time() if now is None else now

    if steward_id:
        clean_steward = str(steward_id).strip()
        clean_event = str(event_id).strip()
        if not clean_steward:
            return {"ok": False, "error": "steward_id cannot be empty"}
        if not clean_event:
            return {"ok": False, "error": "event_id cannot be empty"}

        if norm == "retract":
            store.execute(
                "DELETE FROM nightcal_tallies WHERE event_id = ? AND steward_id = ?",
                (clean_event, clean_steward),
            )
            return {"ok": True, "event_id": clean_event, "steward_id": clean_steward, "direction": "retracted"}

        # Dedup + collapse: upsert single vote per (event_id, steward_id)
        store.execute(
            """
            INSERT INTO nightcal_tallies (event_id, steward_id, direction, verified, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(event_id, steward_id) DO UPDATE SET
                direction = excluded.direction,
                verified = excluded.verified,
                updated_at = excluded.updated_at
            """,
            (clean_event, clean_steward, norm, 1 if verified else 0, timestamp),
        )
        return {
            "ok": True,
            "event_id": clean_event,
            "steward_id": clean_steward,
            "direction": norm,
            "verified": bool(verified),
        }

    # Legacy fallback when no steward_id passed
    row = store.one(
        """
        SELECT l.url AS url
        FROM events e
        JOIN event_listings el ON el.event_id = e.id
        JOIN listings l ON l.id = el.listing_id
        WHERE e.id = ? AND e.active = 1 AND l.url IS NOT NULL
        ORDER BY l.id
        LIMIT 1
        """,
        (event_id,),
    )
    if row and row["url"]:
        col = "ups" if norm == "+" else "downs"
        store.execute(
            f"""
            INSERT INTO nightcal_votes (listing_url, ups, downs)
            VALUES (?, ?, ?)
            ON CONFLICT(listing_url) DO UPDATE SET {col} = nightcal_votes.{col} + 1
            """,
            (row["url"], 1 if norm == "+" else 0, 1 if norm == "−" else 0),
        )
        return {"ok": True, "url": row["url"], "direction": norm}

    return {"ok": False, "error": "event or listing url not found"}


def get_event_tally(store: Store, event_id: str, *, include_unverified: bool = False) -> dict[str, int]:
    """Return tally breakdown for a single event."""
    ensure_votes(store)
    query = """
        SELECT direction, COUNT(*) as cnt
        FROM nightcal_tallies
        WHERE event_id = ?
    """
    params: list[Any] = [event_id]
    if not include_unverified:
        query += " AND verified = 1"
    query += " GROUP BY direction"

    rows = store.query(query, tuple(params))
    counts = {"+": 0, "−": 0}
    for r in rows:
        counts[r["direction"]] = int(r["cnt"])
    return {
        "ups": counts["+"],
        "downs": counts["−"],
        "score": counts["+"] - counts["−"],
        "bodies": counts["+"],
    }


def tally_map(store: Store, *, include_unverified: bool = False) -> dict[str, tuple[int, int]]:
    """Return mapping of event_id -> (ups, downs) for all events with tallies."""
    ensure_votes(store)
    query = "SELECT event_id, direction, COUNT(*) as cnt FROM nightcal_tallies"
    if not include_unverified:
        query += " WHERE verified = 1"
    query += " GROUP BY event_id, direction"

    rows = store.query(query)
    totals: dict[str, dict[str, int]] = {}
    for r in rows:
        totals.setdefault(r["event_id"], {"+": 0, "−": 0})[r["direction"]] = int(r["cnt"])

    return {eid: (d["+"], d["−"]) for eid, d in totals.items()}


def vote_map(store: Store) -> dict[str, tuple[int, int]]:
    """Legacy compatibility: returns listing_url -> (ups, downs)."""
    ensure_votes(store)
    rows = store.query("SELECT listing_url, ups, downs FROM nightcal_votes")
    legacy = {row["listing_url"]: (int(row["ups"]), int(row["downs"])) for row in rows}

    t_map = tally_map(store)
    if t_map:
        url_rows = store.query(
            """
            SELECT el.event_id, l.url
            FROM event_listings el
            JOIN listings l ON l.id = el.listing_id
            WHERE l.url IS NOT NULL
            """
        )
        for ur in url_rows:
            eid = ur["event_id"]
            url = ur["url"]
            if eid in t_map:
                t_ups, t_downs = t_map[eid]
                l_ups, l_downs = legacy.get(url, (0, 0))
                legacy[url] = (l_ups + t_ups, l_downs + t_downs)

    return legacy
