"""SQLite store for flags, nodes, relays, rooms, accords, and ratings.

One connection, shared across threads behind a lock. Single statements
autocommit. ``transaction()`` groups several statements so a write that
fails half way leaves nothing behind.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


class FlagError(Exception):
    """A write the contract refuses. ``code`` is the command-engine error code."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def loads(raw: str | None) -> list[Any]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def load_obj(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS personal_flags (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    holder TEXT NOT NULL,
    linked_flag_id TEXT,
    display_name TEXT NOT NULL,
    bio TEXT NOT NULL DEFAULT '',
    declarations TEXT NOT NULL DEFAULT '[]',
    address TEXT NOT NULL DEFAULT '',
    pgp TEXT,
    availability TEXT NOT NULL DEFAULT '[]',
    skills TEXT NOT NULL DEFAULT '[]',
    offer_title TEXT,
    offer_body TEXT,
    offered_at TEXT,
    link_postings INTEGER NOT NULL DEFAULT 0,
    anonymous INTEGER NOT NULL DEFAULT 1,
    listed INTEGER NOT NULL DEFAULT 0,
    listed_at TEXT,
    place_id TEXT,
    appearance TEXT,
    intents TEXT NOT NULL DEFAULT '[]',
    good_at TEXT NOT NULL DEFAULT '',
    enjoy TEXT NOT NULL DEFAULT '',
    refuse TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_personal_owner_holder
    ON personal_flags(owner, holder);
CREATE TABLE IF NOT EXISTS business_nodes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    inbox TEXT NOT NULL UNIQUE,
    controller TEXT NOT NULL DEFAULT '',
    venue_id TEXT,
    venue_verified INTEGER NOT NULL DEFAULT 0,
    anonymous INTEGER NOT NULL DEFAULT 1,
    listed INTEGER NOT NULL DEFAULT 0,
    listed_at TEXT,
    place_id TEXT,
    appearance TEXT,
    intents TEXT NOT NULL DEFAULT '[]',
    good_at TEXT NOT NULL DEFAULT '',
    enjoy TEXT NOT NULL DEFAULT '',
    refuse TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS business_flags (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES business_nodes(id),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    skills TEXT NOT NULL DEFAULT '[]',
    anonymous INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS relays (
    alias TEXT PRIMARY KEY,
    ref TEXT NOT NULL UNIQUE,
    target TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS introductions (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL UNIQUE,
    buyer TEXT NOT NULL,
    seller TEXT NOT NULL,
    seller_flag_id TEXT NOT NULL,
    sentence TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS room_accords (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL UNIQUE,
    buyer TEXT NOT NULL,
    seller TEXT NOT NULL,
    item TEXT NOT NULL DEFAULT '',
    amount TEXT NOT NULL DEFAULT '',
    unit TEXT NOT NULL DEFAULT '',
    terms TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 0,
    buyer_confirmed INTEGER NOT NULL DEFAULT 0,
    seller_confirmed INTEGER NOT NULL DEFAULT 0,
    buyer_rated INTEGER NOT NULL DEFAULT 0,
    seller_rated INTEGER NOT NULL DEFAULT 0,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS room_obligations (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL,
    buyer TEXT NOT NULL,
    seller TEXT NOT NULL,
    item TEXT NOT NULL,
    amount_xmr TEXT NOT NULL,
    terms TEXT NOT NULL,
    state TEXT NOT NULL,
    paid_tip_xmr TEXT,
    released_tip_xmr TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ratings (
    id TEXT PRIMARY KEY,
    ratee TEXT NOT NULL,
    hearts INTEGER NOT NULL,
    flames INTEGER NOT NULL,
    word TEXT NOT NULL,
    day TEXT NOT NULL
);
"""

# Columns added after the first release. Older databases gain them on open.
_LATE_COLUMNS = {
    "personal_flags": [
        ("listed", "INTEGER NOT NULL DEFAULT 0"),
        ("listed_at", "TEXT"),
        ("offered_at", "TEXT"),
        ("place_id", "TEXT"),
        ("appearance", "TEXT"),
        ("intents", "TEXT NOT NULL DEFAULT '[]'"),
        ("good_at", "TEXT NOT NULL DEFAULT ''"),
        ("enjoy", "TEXT NOT NULL DEFAULT ''"),
        ("refuse", "TEXT NOT NULL DEFAULT ''"),
    ],
    "business_nodes": [
        ("controller", "TEXT NOT NULL DEFAULT ''"),
        ("venue_verified", "INTEGER NOT NULL DEFAULT 0"),
        ("listed", "INTEGER NOT NULL DEFAULT 0"),
        ("listed_at", "TEXT"),
        ("place_id", "TEXT"),
        ("appearance", "TEXT"),
        ("intents", "TEXT NOT NULL DEFAULT '[]'"),
        ("good_at", "TEXT NOT NULL DEFAULT ''"),
        ("enjoy", "TEXT NOT NULL DEFAULT ''"),
        ("refuse", "TEXT NOT NULL DEFAULT ''"),
    ],
}


class FlagStore:
    """Pass a path or ``":memory:"``."""

    def __init__(self, db_path: str | Path = ":memory:"):
        self.db_path = str(db_path)
        self._lock = threading.RLock()
        self._depth = 0
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)
            for table, columns in _LATE_COLUMNS.items():
                have = {row["name"] for row in self._conn.execute(f"PRAGMA table_info({table})")}
                for name, decl in columns:
                    if name not in have:
                        self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
            self._adopt_old_nodes()

    def _adopt_old_nodes(self) -> None:
        """Nodes written before relays used the Steward address as the inbox.

        Move that address to ``controller`` and give the node a relay inbox,
        so the public inbox no longer names the Steward.
        """
        from shadenet.serendipilyst.relay import new_alias

        rows = self._conn.execute(
            "SELECT id, inbox FROM business_nodes WHERE controller = ''"
        ).fetchall()
        for row in rows:
            alias = new_alias()
            self._conn.execute(
                "UPDATE business_nodes SET controller = ?, inbox = ? WHERE id = ?",
                (row["inbox"], alias, row["id"]),
            )
            self._conn.execute(
                "INSERT OR IGNORE INTO relays (alias, ref, target, created_at) VALUES (?, ?, ?, ?)",
                (alias, f"node:{row['id']}", row["inbox"], now_iso()),
            )

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Group writes. Nested calls join the outer transaction."""
        with self._lock:
            outer = self._depth == 0
            if outer:
                self._conn.execute("BEGIN IMMEDIATE")
            self._depth += 1
            try:
                yield
            except BaseException:
                self._depth -= 1
                if outer:
                    self._conn.execute("ROLLBACK")
                raise
            self._depth -= 1
            if outer:
                self._conn.execute("COMMIT")

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def query_all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, params).fetchall())
