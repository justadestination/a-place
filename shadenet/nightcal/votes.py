"""Thumbs on a cited show.

The count is stored against the listing URL, not the event id. A
re-resolve can mint a new event id when a venue fact changes. The URL
the calendar printed does not.
"""

from __future__ import annotations

from shadenet.towncrier.store import Store


def ensure_votes(store: Store) -> None:
    store.execute(
        """
        CREATE TABLE IF NOT EXISTS nightcal_votes (
            listing_url TEXT PRIMARY KEY,
            ups INTEGER NOT NULL DEFAULT 0,
            downs INTEGER NOT NULL DEFAULT 0
        )
        """
    )


def record_vote(store: Store, event_id: str, direction: str) -> None:
    if direction not in ("up", "down"):
        return
    ensure_votes(store)
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
    if row is None or not row["url"]:
        return
    ups = 1 if direction == "up" else 0
    downs = 1 if direction == "down" else 0
    column = "ups" if direction == "up" else "downs"
    store.execute(
        f"""
        INSERT INTO nightcal_votes (listing_url, ups, downs)
        VALUES (?, ?, ?)
        ON CONFLICT(listing_url) DO UPDATE SET {column} = nightcal_votes.{column} + 1
        """,
        (row["url"], ups, downs),
    )


def vote_map(store: Store) -> dict[str, tuple[int, int]]:
    ensure_votes(store)
    rows = store.query("SELECT listing_url, ups, downs FROM nightcal_votes")
    return {row["listing_url"]: (int(row["ups"]), int(row["downs"])) for row in rows}
