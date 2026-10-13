"""Unit and abuse tests for embedded Matrix chat engine (Task 5.1)."""

import sqlite3
import pytest
from pathlib import Path

from shadenet.chat import (
    DOMAIN,
    STEWARD_PSEUDONYM,
    get_db,
    get_pseudonym_for_user,
    list_rooms,
    post_message,
    get_room_messages,
    moderate_message,
    is_pseudonym_banned,
)


@pytest.fixture
def chat_db(tmp_path):
    db_file = tmp_path / "chat_test.db"
    conn = get_db(db_file)
    # Seed sample events for steward response testing
    conn.execute("""
        CREATE TABLE IF NOT EXISTS venues (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            closed INTEGER DEFAULT 0
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            starts_at TEXT NOT NULL,
            venue_id TEXT,
            active INTEGER DEFAULT 1
        );
    """)
    conn.execute("INSERT INTO venues (id, name) VALUES ('ven_echo', 'Echo Music Hall')")
    conn.execute("INSERT INTO events (id, title, starts_at, venue_id, active) VALUES ('evt_1', 'The Midnight Echoes', '8:00 PM', 'ven_echo', 1)")
    conn.commit()
    yield conn
    conn.close()


def test_pseudonym_anonymity_and_stability(chat_db):
    user_a = "user_secret_uuid_123"
    user_b = "user_secret_uuid_456"

    pseudo_a1 = get_pseudonym_for_user(chat_db, user_a)
    pseudo_a2 = get_pseudonym_for_user(chat_db, user_a)
    pseudo_b = get_pseudonym_for_user(chat_db, user_b)

    # Stability
    assert pseudo_a1 == pseudo_a2
    assert pseudo_a1.startswith("@anon-")
    assert pseudo_a1.endswith(f":{DOMAIN}")

    # Distinctness and anonymity: neither contains the real user ID
    assert pseudo_a1 != pseudo_b
    assert "secret_uuid_123" not in pseudo_a1
    assert "secret_uuid_456" not in pseudo_b


def test_list_rooms_and_seed_content(chat_db):
    rooms = list_rooms(chat_db)
    assert len(rooms) >= 1
    general = next(r for r in rooms if r["alias"] == f"#downtown-general:{DOMAIN}")
    assert general["name"] == "Downtown General"
    assert general["message_count"] >= 1  # Welcome message from steward


def test_post_and_retrieve_messages(chat_db):
    rooms = list_rooms(chat_db)
    general_id = rooms[0]["room_id"]
    pseudo = get_pseudonym_for_user(chat_db, "user_patron")

    result = post_message(chat_db, general_id, pseudo, "Heading down to 5th Street soon!")
    assert result["event_id"].startswith("$m_")
    assert result["sender"] == pseudo
    assert result["content"] == "Heading down to 5th Street soon!"

    messages = get_room_messages(chat_db, general_id)
    patron_msg = next(m for m in messages if m["event_id"] == result["event_id"])
    assert patron_msg["content"] == "Heading down to 5th Street soon!"
    assert patron_msg["sender"] == pseudo


def test_steward_in_room_assistant_triggers(chat_db):
    rooms = list_rooms(chat_db)
    general_id = rooms[0]["room_id"]
    pseudo = get_pseudonym_for_user(chat_db, "user_curious")

    # Asking what's on tonight triggers Steward
    result = post_message(chat_db, general_id, pseudo, "Hey @steward, what's on tonight?")
    assert "steward_reply" in result
    steward_reply = result["steward_reply"]
    assert steward_reply["sender"] == STEWARD_PSEUDONYM
    assert "The Midnight Echoes" in steward_reply["content"]
    assert "Echo Music Hall" in steward_reply["content"]

    # Steward reply persisted in room messages
    messages = get_room_messages(chat_db, general_id)
    assert any(m["sender"] == STEWARD_PSEUDONYM and "The Midnight Echoes" in m["content"] for m in messages)


def test_operator_moderation_redact_and_ban(chat_db):
    rooms = list_rooms(chat_db)
    general_id = rooms[0]["room_id"]
    spammer = get_pseudonym_for_user(chat_db, "spammer_999")

    # Post message
    res = post_message(chat_db, general_id, spammer, "Buy cheap sunglasses here!")
    msg_id = res["event_id"]

    # Redact message
    mod_res = moderate_message(chat_db, "operator_mod", "redact", msg_id)
    assert mod_res["status"] == "redacted"

    messages = get_room_messages(chat_db, general_id)
    redacted_msg = next(m for m in messages if m["event_id"] == msg_id)
    assert redacted_msg["redacted"] is True
    assert "[Message redacted" in redacted_msg["content"]

    # Ban spammer pseudonym
    ban_res = moderate_message(chat_db, "operator_mod", "ban", spammer, "Spamming")
    assert ban_res["status"] == "banned"
    assert is_pseudonym_banned(chat_db, spammer)

    # Spammer cannot send further messages
    with pytest.raises(PermissionError, match="is banned from chat"):
        post_message(chat_db, general_id, spammer, "Another spam attempt")


def test_private_room_stays_off_the_public_list(chat_db):
    from shadenet.chat import create_private_room

    buyer = get_pseudonym_for_user(chat_db, "buyer")
    seller = get_pseudonym_for_user(chat_db, "seller")
    room = create_private_room(
        chat_db,
        name="Lumen",
        topic="A tube amp.",
        members=[STEWARD_PSEUDONYM, buyer, seller],
        opening="I told their steward. This room is private.",
    )
    public = list_rooms(chat_db)
    assert any(item["name"] == "Downtown General" for item in public)
    assert all(item["room_id"] != room["room_id"] for item in public)
    seen = get_room_messages(chat_db, room["room_id"], viewer=buyer)
    assert any("private" in item["content"] for item in seen)
    with pytest.raises(PermissionError):
        get_room_messages(chat_db, room["room_id"])
    with pytest.raises(PermissionError):
        post_message(chat_db, room["room_id"], f"@anon-outsider:{DOMAIN}", "hello")
