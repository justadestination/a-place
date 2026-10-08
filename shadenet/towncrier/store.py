"""Storage layer for towncrier.

Thin wrapper over sqlite3. Deliberately not an ORM: the queries here are few,
specific, and performance-sensitive (a scan touches thousands of rows), and an
ORM would hide exactly the query plans that matter here.

Conventions:
  * All datetimes are ISO 8601 strings in UTC unless suffixed with an offset.
  * Event starts are stored in UTC; the original offset is kept on the event
    row as `timezone` so the .ics feed can render local time correctly. Storing
    a naive local time is the classic bug that makes a recurring feed drift an
    hour twice a year.
  * `ensure_*` helpers are idempotent. Scans re-run against the same sources
    constantly, so every write path must tolerate re-entry.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def utcnow() -> str:
    """Current time as an ISO 8601 UTC string with second precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_id(prefix: str, *parts: str) -> str:
    """Deterministic id from parts.

    Stability matters: re-running a scan must not mint new ids for the same
    venue, or every event would re-point at fresh rows each cycle.
    """
    raw = "\x1f".join(p.strip().lower() for p in parts if p)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def slugify(value: str) -> str:
    """ASCII slug, used for venue/artist ids."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    out = "".join(c if c.isalnum() else "-" for c in ascii_only.lower())
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "unknown"


class Store:
    """Owns the database connection and the schema."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA_PATH.read_text())

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """Explicit transaction. Scans write a lot; one commit per scan is
        both faster and safer than autocommit per row."""
        self._conn.execute("BEGIN")
        try:
            yield self._conn
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")

    # ---------------------------------------------------------------- queries

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self._conn.execute(sql, tuple(params)).fetchall()

    def one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self._conn.execute(sql, tuple(params)).fetchone()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, tuple(params))

    # ---------------------------------------------------------------- sources

    def upsert_source(
        self,
        source_id: str,
        kind: str,
        base_url: str | None = None,
        interval_min: int = 60,
        min_delay_sec: float = 5.0,
        enabled: bool = True,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO sources (id, kind, base_url, interval_min, min_delay_sec, enabled)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                kind = excluded.kind,
                base_url = excluded.base_url,
                interval_min = excluded.interval_min,
                min_delay_sec = excluded.min_delay_sec
            """,
            (source_id, kind, base_url, interval_min, min_delay_sec, int(enabled)),
        )

    def due_sources(self, now: str | None = None) -> list[sqlite3.Row]:
        """Sources whose interval has elapsed.

        A source that keeps failing is skipped rather than retried in a tight
        loop: a venue taking their site down should not turn into a hot loop
        against it.
        """
        now = now or utcnow()
        return self.query(
            """
            SELECT * FROM sources
            WHERE enabled = 1
              AND (last_polled_at IS NULL
                   OR julianday(?) - julianday(last_polled_at)
                      >= (interval_min / 1440.0))
              AND consecutive_failures < 10
            """,
            (now,),
        )

    def record_scan_result(
        self,
        source_id: str,
        status: str,
        error_kind: str | None = None,
        http_status: int | None = None,
        seen: int = 0,
        new: int = 0,
        changed: int = 0,
        gone: int = 0,
        duration_ms: int | None = None,
        detail: str | None = None,
    ) -> int:
        """Record a completed scan and update the source's health counters.

        Returns the scan id so the caller can attach listings/changes to it.
        """
        cur = self._conn.execute(
            """
            INSERT INTO scans (source_id, started_at, finished_at, status, error_kind,
                               http_status, listings_seen, listings_new,
                               listings_changed, listings_gone, duration_ms, detail)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id, utcnow(), utcnow(), status, error_kind, http_status,
                seen, new, changed, gone, duration_ms, detail,
            ),
        )
        scan_id = cur.lastrowid or 0
        failures = 0 if status == "ok" else None
        self._conn.execute(
            """
            UPDATE sources
            SET last_polled_at = ?,
                last_status = ?,
                consecutive_failures = CASE WHEN ? = 'ok' THEN 0
                                           ELSE consecutive_failures + 1 END
            WHERE id = ?
            """,
            (utcnow(), status, status, source_id),
        )
        del failures
        return scan_id

    def start_scan(self, source_id: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO scans (source_id, status) VALUES (?, 'running')",
            (source_id,),
        )
        return cur.lastrowid or 0

    def finish_scan(self, scan_id: int, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        self._conn.execute(
            f"UPDATE scans SET {cols} WHERE id = ?", (*fields.values(), scan_id)
        )

    # ---------------------------------------------------------------- listings

    def get_listing(self, source_id: str, external_id: str) -> sqlite3.Row | None:
        return self.one(
            "SELECT * FROM listings WHERE source_id = ? AND external_id = ?",
            (source_id, external_id),
        )

    def upsert_listing(
        self,
        *,
        source_id: str,
        external_id: str,
        url: str | None,
        title_raw: str,
        title_norm: str,
        starts_at: str | None,
        ends_at: str | None = None,
        all_day: bool = False,
        status: str = "EventScheduled",
        venue_id: str | None = None,
        venue_name_raw: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        ticket_url: str | None = None,
        price: str | None = None,
        image_url: str | None = None,
        description: str | None = None,
        raw_json: dict | None = None,
    ) -> tuple[int, str, dict[str, Any]]:
        """Insert or update a listing.

        Returns (listing_id, action, diffs) where action is 'new' | 'unchanged'
        | 'changed'. We compare before writing so we only record an event change
        when something genuinely moved — otherwise every scan would flag every
        event as changed and the change log would be noise.
        """
        existing = self.get_listing(source_id, external_id)
        if existing is None:
            cur = self._conn.execute(
                """
                INSERT INTO listings (source_id, external_id, url, title_raw, title_norm,
                                      description, starts_at, ends_at, all_day, status,
                                      venue_id, venue_name_raw, lat, lon, ticket_url,
                                      price, image_url, last_seen_at, raw_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    source_id, external_id, url, title_raw, title_norm, description,
                    starts_at, ends_at, int(all_day), status, venue_id, venue_name_raw,
                    lat, lon, ticket_url, price, image_url, utcnow(),
                    json.dumps(raw_json) if raw_json else None,
                ),
            )
            return int(cur.lastrowid or 0), "new", {}

        # What actually changed? Compare only fields that affect identity or
        # lifecycle; description churn should not count as a real change.
        watched = ("starts_at", "ends_at", "status", "title_norm", "venue_id", "ticket_url")
        diffs = {
            k: (existing[k], new)
            for k, new in (
                ("starts_at", starts_at),
                ("ends_at", ends_at),
                ("status", status),
                ("title_norm", title_norm),
                ("venue_id", venue_id),
                ("ticket_url", ticket_url),
            )
            if existing[k] != new
        }
        self._conn.execute(
            """
            UPDATE listings
            SET url = ?, title_raw = ?, title_norm = ?, description = ?, starts_at = ?,
                ends_at = ?, all_day = ?, status = ?, venue_id = ?, venue_name_raw = ?,
                lat = ?, lon = ?, ticket_url = ?, price = ?, image_url = ?,
                last_seen_at = ?, missing_since = NULL, missing_count = 0,
                raw_json = COALESCE(?, raw_json)
            WHERE id = ?
            """,
            (
                url, title_raw, title_norm, description, starts_at, ends_at,
                int(all_day), status, venue_id, venue_name_raw, lat, lon,
                ticket_url, price, image_url, utcnow(),
                json.dumps(raw_json) if raw_json else None,
                existing["id"],
            ),
        )
        action = "changed" if diffs else "unchanged"
        return int(existing["id"]), action, diffs

    def listings_for_source(self, source_id: str) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM listings WHERE source_id = ?", (source_id,))

    def mark_listings_missing(self, source_id: str, seen_ids: set[str], reason: str) -> list[int]:
        """Flag listings from this source that were not in this scan.

        This is the raw signal for cancellation. We do not delete: an
        event list that rotates is not a cancellation, so the row is marked
        and the caller decides based on corroboration and how long it has
        been gone.
        """
        rows = self.listings_for_source(source_id)
        gone = [
            r["id"] for r in rows
            if r["external_id"] not in seen_ids and r["missing_since"] is None
        ]
        if gone:
            placeholders = ",".join("?" * len(gone))
            self._conn.execute(
                f"""
                UPDATE listings
                SET missing_since = ?, missing_count = missing_count + 1
                WHERE id IN ({placeholders})
                """,
                (utcnow(), *gone),
            )
            del reason
        return gone

    def restore_listing(self, listing_id: int) -> None:
        self._conn.execute(
            "UPDATE listings SET missing_since = NULL, missing_count = 0 WHERE id = ?",
            (listing_id,),
        )

    # ---------------------------------------------------------------- events

    def get_event(self, event_id: str) -> sqlite3.Row | None:
        return self.one("SELECT * FROM events WHERE id = ?", (event_id,))

    def insert_event(self, **fields: Any) -> str:
        event_id = fields.pop("id")
        cols = ", ".join(fields)
        marks = ", ".join("?" * (len(fields) + 1))
        self._conn.execute(
            f"INSERT INTO events (id, {cols}) VALUES ({marks})",
            (event_id, *fields.values()),
        )
        return event_id

    def update_event(self, event_id: str, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        self._conn.execute(
            f"UPDATE events SET {cols} WHERE id = ?", (*fields.values(), event_id)
        )

    def record_change(
        self,
        event_id: str,
        field: str,
        old_value: Any,
        new_value: Any,
        reason: str | None = None,
        scan_id: int | None = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO event_changes (event_id, field, old_value, new_value, reason, scan_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, field, _as_text(old_value), _as_text(new_value), reason, scan_id),
        )

    # ---------------------------------------------------------------- venues

    def ensure_venue(
        self,
        name: str,
        *,
        address: str | None = None,
        city: str | None = None,
        state: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        website: str | None = None,
    ) -> str:
        venue_id = stable_id("ven", name, address or "")
        self._conn.execute(
            """
            INSERT INTO venues (id, name, address, city, state, lat, lon, website)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                address = COALESCE(excluded.address, venues.address),
                city    = COALESCE(excluded.city, venues.city),
                state   = COALESCE(excluded.state, venues.state),
                lat     = COALESCE(excluded.lat, venues.lat),
                lon     = COALESCE(excluded.lon, venues.lon),
                website = COALESCE(excluded.website, venues.website),
                updated_at = datetime('now')
            """,
            (venue_id, name, address, city, state, lat, lon, website),
        )
        return venue_id

    def get_venue(self, venue_id: str) -> sqlite3.Row | None:
        return self.one("SELECT * FROM venues WHERE id = ?", (venue_id,))

    # ---------------------------------------------------------------- entities
    #
    # The tree layer. `venues` above is a denormalized convenience for the
    # resolver's hot path; `entities` is the canonical record and the one
    # carrying items and citations.

    def get_entity(self, entity_id: str) -> sqlite3.Row | None:
        return self.one("SELECT * FROM entities WHERE id = ?", (entity_id,))

    def entity_by_name(self, name: str, kind: str) -> sqlite3.Row | None:
        return self.one(
            "SELECT * FROM entities WHERE name = ? AND kind = ? COLLATE NOCASE",
            (name, kind),
        )

    # ---------------------------------------------------------------- performers

    def ensure_performer(
        self,
        name: str,
        *,
        kind: str = "unknown",
        external_ids: dict | None = None,
    ) -> str:
        performer_id = stable_id("per", name)
        self._conn.execute(
            """
            INSERT INTO performers (id, name, kind, external_ids)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                kind = CASE WHEN performers.kind = 'unknown' THEN excluded.kind
                            ELSE performers.kind END,
                external_ids = CASE
                    WHEN excluded.external_ids = '{}' THEN performers.external_ids
                    ELSE performers.external_ids END,
                updated_at = datetime('now')
            """,
            (performer_id, name, kind, json.dumps(external_ids or {})),
        )
        return performer_id

    def get_performer(self, performer_id: str) -> sqlite3.Row | None:
        return self.one("SELECT * FROM performers WHERE id = ?", (performer_id,))

    def link_performer(
        self, event_id: str, performer_id: str, billing: str = "unknown", display_name: str | None = None
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO event_performers (event_id, performer_id, billing, display_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(event_id, performer_id) DO UPDATE SET
                billing = CASE WHEN excluded.billing = 'unknown' THEN event_performers.billing
                               ELSE excluded.billing END
            """,
            (event_id, performer_id, billing, display_name),
        )


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)
