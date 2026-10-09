"""Embedded Matrix-compatible chat engine for ShadeNet (Task 5.1).

Carries a self-contained chat server backed by SQLite (shadenet.db):
1. Zero-step transparent authentication: mints anonymous pseudonyms
   (@anon-<hash>:shady.example.org) from Steward / session tokens.
2. Server-side pseudonym mapping: real user IDs are never leaked to other chatters.
3. Room topology: Domain-general (#downtown-general) + Space rooms per venue.
4. Steward in-room bot: answers "what's on tonight?" directly from live calendar data.
5. Operator moderation: redact messages and ban disruptive pseudonyms.
6. Matrix Client-Server v3 API compatibility layer + REST endpoints.
7. External hook/bridge metadata for chat.example.org.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

DOMAIN = os.environ.get("SHADENET_DOMAIN", "shady.example.org")
EXTERNAL_MATRIX_URL = os.environ.get("MATRIX_HOMESERVER_URL", "https://chat.example.org")
CHAT_SALT = os.environ.get("CHAT_PSEUDONYM_SALT", "shadenet-steward-anon-salt-2026")
STEWARD_PSEUDONYM = f"@steward:{DOMAIN}"

DEFAULT_DB = Path(__file__).resolve().parent / "data" / "shadenet.db"


def get_db(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target = Path(db_path) if db_path else DEFAULT_DB
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_chat_schema(conn)
    return conn


def init_chat_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chat_rooms (
            id TEXT PRIMARY KEY,
            alias TEXT UNIQUE,
            name TEXT NOT NULL,
            topic TEXT NOT NULL,
            kind TEXT NOT NULL, -- 'domain' | 'space'
            venue_id TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_pseudonyms (
            user_id TEXT PRIMARY KEY,
            pseudonym TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL REFERENCES chat_rooms(id) ON DELETE CASCADE,
            sender TEXT NOT NULL,
            content TEXT NOT NULL,
            msgtype TEXT NOT NULL DEFAULT 'm.text',
            timestamp INTEGER NOT NULL, -- unix ms
            redacted INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_bans (
            pseudonym TEXT PRIMARY KEY,
            reason TEXT NOT NULL,
            banned_by TEXT NOT NULL,
            banned_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_chat_messages_room_ts
        ON chat_messages(room_id, timestamp DESC);
    """)
    conn.commit()
    seed_default_rooms(conn)


def seed_default_rooms(conn: sqlite3.Connection) -> None:
    # Ensure domain-general room exists
    general_id = f"!general:{DOMAIN}"
    general_alias = f"#downtown-general:{DOMAIN}"
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    
    cur = conn.cursor()
    cur.execute("SELECT id FROM chat_rooms WHERE id = ?", (general_id,))
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO chat_rooms (id, alias, name, topic, kind, venue_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                general_id,
                general_alias,
                "Downtown General",
                "Community chat for Downtown Santa Rosa nights, shows, and patron conversation.",
                "domain",
                None,
                now_iso,
            ),
        )
        # Welcome message from steward
        welcome_id = f"$m_{uuid.uuid4().hex[:12]}"
        now_ms = int(time.time() * 1000)
        cur.execute(
            """INSERT INTO chat_messages (id, room_id, sender, content, msgtype, timestamp, redacted, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                welcome_id,
                general_id,
                STEWARD_PSEUDONYM,
                "Welcome to Downtown General. Room messages persist and are public to all patrons. Ask me 'what's on tonight?' for listings.",
                "m.text",
                now_ms,
                0,
                now_iso,
            ),
        )

    # Sync venue rooms from venues table if present
    try:
        cur.execute("SELECT id, name FROM venues WHERE status = 'active' OR closed = 0 LIMIT 20")
        venues = cur.fetchall()
        for v in venues:
            vid = v["id"]
            slug = vid.replace("ven_", "").replace("_", "-")
            room_id = f"!venue_{slug}:{DOMAIN}"
            alias = f"#{slug}:{DOMAIN}"
            vname = v["name"] or f"Venue {slug}"
            cur.execute("SELECT id FROM chat_rooms WHERE id = ?", (room_id,))
            if not cur.fetchone():
                cur.execute(
                    """INSERT INTO chat_rooms (id, alias, name, topic, kind, venue_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        room_id,
                        alias,
                        vname,
                        f"Live room for {vname}. Discuss upcoming shows and tonight's scene.",
                        "space",
                        vid,
                        now_iso,
                    ),
                )
    except sqlite3.OperationalError:
        pass
    conn.commit()


def get_pseudonym_for_user(conn: sqlite3.Connection, user_id: str) -> str:
    """Deterministically derive and persist an anonymous pseudonym for a user/session.
    
    Zero user steps: User ID is never exposed; pseudonym is stable per account.
    """
    if not user_id:
        user_id = "guest_" + uuid.uuid4().hex[:8]
        
    cur = conn.cursor()
    cur.execute("SELECT pseudonym FROM chat_pseudonyms WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row:
        return row["pseudonym"]

    # Compute short cryptographic pseudonym
    raw_hash = hashlib.sha256(f"{user_id}:{CHAT_SALT}".encode("utf-8")).hexdigest()
    pseudonym = f"@anon-{raw_hash[:8]}:{DOMAIN}"
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    cur.execute(
        "INSERT INTO chat_pseudonyms (user_id, pseudonym, created_at) VALUES (?, ?, ?)",
        (user_id, pseudonym, now_iso),
    )
    conn.commit()
    return pseudonym


def is_pseudonym_banned(conn: sqlite3.Connection, pseudonym: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM chat_bans WHERE pseudonym = ?", (pseudonym,))
    return cur.fetchone() is not None


def list_rooms(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute("""
        SELECT r.id, r.alias, r.name, r.topic, r.kind, r.venue_id, r.created_at,
               (SELECT COUNT(*) FROM chat_messages m WHERE m.room_id = r.id AND m.redacted = 0) as message_count,
               (SELECT content FROM chat_messages m WHERE m.room_id = r.id AND m.redacted = 0 ORDER BY m.timestamp DESC LIMIT 1) as last_message,
               (SELECT timestamp FROM chat_messages m WHERE m.room_id = r.id AND m.redacted = 0 ORDER BY m.timestamp DESC LIMIT 1) as last_activity
        FROM chat_rooms r
        ORDER BY r.kind ASC, r.created_at ASC
    """)
    rows = cur.fetchall()
    return [
        {
            "room_id": r["id"],
            "alias": r["alias"],
            "name": r["name"],
            "topic": r["topic"],
            "kind": r["kind"],
            "venue_id": r["venue_id"],
            "message_count": r["message_count"],
            "last_message": r["last_message"] or "",
            "last_activity": r["last_activity"] or 0,
        }
        for r in rows
    ]


def get_room_messages(
    conn: sqlite3.Connection, room_id: str, limit: int = 50, since_ts: int = 0
) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    query = """
        SELECT id, room_id, sender, content, msgtype, timestamp, redacted, created_at
        FROM chat_messages
        WHERE room_id = ? AND timestamp > ?
        ORDER BY timestamp ASC
        LIMIT ?
    """
    cur.execute(query, (room_id, since_ts, limit))
    rows = cur.fetchall()
    out = []
    for r in rows:
        redacted = bool(r["redacted"])
        out.append({
            "event_id": r["id"],
            "room_id": r["room_id"],
            "sender": r["sender"],
            "content": "[Message redacted by operator]" if redacted else r["content"],
            "msgtype": r["msgtype"],
            "timestamp": r["timestamp"],
            "redacted": redacted,
            "created_at": r["created_at"],
        })
    return out


def synthesize_steward_response(conn: sqlite3.Connection, venue_id: Optional[str] = None) -> str:
    """Generate calendar-aware assistance from tonight's spots."""
    try:
        cur = conn.cursor()
        if venue_id:
            cur.execute("""
                SELECT e.title, e.starts_at, v.name as venue_name
                FROM events e
                JOIN venues v ON e.venue_id = v.id
                WHERE e.venue_id = ? AND e.active = 1
                ORDER BY e.starts_at ASC
                LIMIT 3
            """, (venue_id,))
        else:
            cur.execute("""
                SELECT e.title, e.starts_at, v.name as venue_name
                FROM events e
                JOIN venues v ON e.venue_id = v.id
                WHERE e.active = 1
                ORDER BY e.starts_at ASC
                LIMIT 4
            """)
        events = cur.fetchall()
        if not events:
            return "No shows currently scheduled for tonight. Check back soon or visit the /today timeline for upcoming dates."

        lines = ["Here's what's on tonight in Downtown Santa Rosa:"]
        for ev in events:
            vname = ev["venue_name"] or "Downtown"
            time_str = ev["starts_at"] or "Tonight"
            lines.append(f"• {ev['title']} at {vname} ({time_str})")
        lines.append("Head to the /today page to mark your attendance (+/− Bodies) or earmark tickets.")
        return "\n".join(lines)
    except Exception:
        return "Tonight's calendar is live on the /today timeline with full showtimes and lineups."


def post_message(
    conn: sqlite3.Connection, room_id: str, sender_pseudonym: str, content: str
) -> Dict[str, Any]:
    if is_pseudonym_banned(conn, sender_pseudonym):
        raise PermissionError(f"{sender_pseudonym} is banned from chat")

    content = content.strip()
    if not content:
        raise ValueError("Message content cannot be empty")
    if len(content) > 4000:
        raise ValueError("Message exceeds 4000 character limit")

    event_id = f"$m_{uuid.uuid4().hex[:12]}"
    now_ms = int(time.time() * 1000)
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    cur = conn.cursor()
    # Verify room exists
    cur.execute("SELECT id, venue_id FROM chat_rooms WHERE id = ?", (room_id,))
    room = cur.fetchone()
    if not room:
        raise ValueError(f"Room {room_id} does not exist")

    cur.execute(
        """INSERT INTO chat_messages (id, room_id, sender, content, msgtype, timestamp, redacted, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_id, room_id, sender_pseudonym, content, "m.text", now_ms, 0, now_iso),
    )
    conn.commit()

    result = {
        "event_id": event_id,
        "room_id": room_id,
        "sender": sender_pseudonym,
        "content": content,
        "msgtype": "m.text",
        "timestamp": now_ms,
        "redacted": False,
    }

    # Check for Steward question triggers
    lower = content.lower()
    steward_triggers = [
        "@steward", "what's on tonight", "whats on tonight", "what is on tonight",
        "who's playing", "whos playing", "what shows", "any live music",
    ]
    if any(trigger in lower for trigger in steward_triggers):
        steward_reply = synthesize_steward_response(conn, room["venue_id"])
        steward_event_id = f"$m_{uuid.uuid4().hex[:12]}"
        steward_ts = now_ms + 100
        cur.execute(
            """INSERT INTO chat_messages (id, room_id, sender, content, msgtype, timestamp, redacted, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (steward_event_id, room_id, STEWARD_PSEUDONYM, steward_reply, "m.text", steward_ts, 0, now_iso),
        )
        conn.commit()
        result["steward_reply"] = {
            "event_id": steward_event_id,
            "sender": STEWARD_PSEUDONYM,
            "content": steward_reply,
            "timestamp": steward_ts,
        }

    return result


def moderate_message(
    conn: sqlite3.Connection,
    operator_user: str,
    action: str,
    target_id: str,
    reason: str = "Operator action",
) -> Dict[str, Any]:
    """Moderate chat: 'redact' message or 'ban' user pseudonym."""
    cur = conn.cursor()
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if action == "redact":
        cur.execute("UPDATE chat_messages SET redacted = 1 WHERE id = ?", (target_id,))
        conn.commit()
        return {"action": "redact", "message_id": target_id, "status": "redacted"}

    if action == "ban":
        cur.execute(
            "INSERT OR REPLACE INTO chat_bans (pseudonym, reason, banned_by, banned_at) VALUES (?, ?, ?, ?)",
            (target_id, reason, operator_user, now_iso),
        )
        conn.commit()
        return {"action": "ban", "pseudonym": target_id, "status": "banned"}

    raise ValueError(f"Unknown moderation action: {action}")
