"""SQLite store for personal flags, business nodes, and business flags."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class FlagError(Exception):
    """A flag or node write that the contract refuses."""

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


class FlagStore:
    """One connection, created on open. Pass a path or ``\":memory:\"``."""

    def __init__(self, db_path: str | Path = ":memory:"):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def close(self) -> None:
        self._conn.close()

    def _migrate(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS personal_flags (
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                display_name TEXT NOT NULL,
                bio TEXT NOT NULL DEFAULT '',
                declarations TEXT NOT NULL DEFAULT '[]',
                address TEXT NOT NULL,
                pgp TEXT,
                availability TEXT NOT NULL DEFAULT '[]',
                skills TEXT NOT NULL DEFAULT '[]',
                offer_title TEXT,
                offer_body TEXT,
                link_postings INTEGER NOT NULL DEFAULT 0,
                anonymous INTEGER NOT NULL DEFAULT 1,
                holder TEXT NOT NULL,
                linked_flag_id TEXT,
                listed INTEGER NOT NULL DEFAULT 0,
                place_id TEXT,
                appearance TEXT,
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
                venue_id TEXT,
                anonymous INTEGER NOT NULL DEFAULT 1,
                listed INTEGER NOT NULL DEFAULT 0,
                place_id TEXT,
                appearance TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS introductions (
                id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL,
                buyer TEXT NOT NULL,
                seller TEXT NOT NULL,
                seller_flag_id TEXT NOT NULL,
                sentence TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS accords (
                id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL UNIQUE,
                buyer TEXT NOT NULL,
                seller TEXT NOT NULL,
                seller_flag_id TEXT NOT NULL,
                buyer_give TEXT NOT NULL DEFAULT '',
                buyer_get TEXT NOT NULL DEFAULT '',
                buyer_amount TEXT NOT NULL DEFAULT '',
                seller_give TEXT NOT NULL DEFAULT '',
                seller_get TEXT NOT NULL DEFAULT '',
                seller_amount TEXT NOT NULL DEFAULT '',
                thing TEXT NOT NULL DEFAULT '',
                amount_xmr TEXT NOT NULL DEFAULT '',
                buyer_confirmed INTEGER NOT NULL DEFAULT 0,
                seller_confirmed INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS obligations (
                id TEXT PRIMARY KEY,
                buyer TEXT NOT NULL,
                seller TEXT NOT NULL,
                seller_flag_id TEXT NOT NULL,
                sentence TEXT NOT NULL,
                amount_xmr TEXT NOT NULL,
                state TEXT NOT NULL,
                paid_tip_xmr TEXT,
                released_tip_xmr TEXT,
                buyer_personal INTEGER,
                buyer_product INTEGER,
                buyer_word TEXT,
                seller_personal INTEGER,
                seller_product INTEGER,
                seller_word TEXT,
                room_id TEXT,
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
            """
        )
        self._add_columns("personal_flags", [
            ("listed", "INTEGER NOT NULL DEFAULT 0"),
            ("place_id", "TEXT"),
            ("appearance", "TEXT"),
            ("intents", "TEXT NOT NULL DEFAULT '[]'"),
            ("good_at", "TEXT NOT NULL DEFAULT ''"),
            ("enjoy", "TEXT NOT NULL DEFAULT ''"),
            ("refuse", "TEXT NOT NULL DEFAULT ''"),
        ])
        self._add_columns("business_nodes", [
            ("listed", "INTEGER NOT NULL DEFAULT 0"),
            ("place_id", "TEXT"),
            ("appearance", "TEXT"),
            ("intents", "TEXT NOT NULL DEFAULT '[]'"),
            ("good_at", "TEXT NOT NULL DEFAULT ''"),
            ("enjoy", "TEXT NOT NULL DEFAULT ''"),
            ("refuse", "TEXT NOT NULL DEFAULT ''"),
        ])
        self._conn.commit()

    def _add_columns(self, table: str, columns: list[tuple[str, str]]) -> None:
        have = {row["name"] for row in self._conn.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns:
            if name not in have:
                self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        cur = self._conn.execute(sql, params)
        self._conn.commit()
        return cur

    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self._conn.execute(sql, params).fetchone()

    def query_all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return list(self._conn.execute(sql, params).fetchall())
