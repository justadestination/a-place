"""The private room, the accord, and ratings.

Serendipilyst introduces people and writes down what they agreed. A price
in XMR can go on to a Monero obligation to the platform (``obligation.py``);
any other price is settled between the two people, off the platform.

1. ``introduce``: interest in a flag opens a private room for the two
   Stewards' people and the house Steward.
2. ``read_accord``: either person asks the Steward to read the room. One
   model call writes down the item and price (see ``reader``). Each reading
   gets a new ``terms`` code and clears earlier confirmations.
3. ``confirm_accord``: each person confirms the ``terms`` code they were
   shown. When both confirm the same code, the room is accorded.
4. ``rate``: after an accord, each person may leave hearts, flames, and one
   word about the other. A rating is stored against the person rated only,
   without the rater, the room, or the time of day.
5. ``counsel``: the Steward speaks about ratings only after a sample.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from shadenet.serendipilyst.fields import actor as check_actor, one_sentence
from shadenet.serendipilyst.reader import read_terms
from shadenet.serendipilyst.relay import PREFIX, resolve
from shadenet.serendipilyst.store import FlagError, FlagStore, loads, new_id, now_iso

SAMPLE = 25
WORD = re.compile(r"^[A-Za-z][A-Za-z'-]{0,23}$")


def _require_chat(chat: Any) -> Any:
    if chat is None:
        raise FlagError("chat_unavailable", "The rooms are closed right now.")
    return chat


def _target(store: FlagStore, ref: str) -> dict[str, Any]:
    """Who stands behind a flag id, node id, business flag id, or relay alias."""
    if ref.startswith(PREFIX):
        behind = resolve(store, ref)["ref"]
        kind, _, rest = behind.partition(":")
        if kind == "offer":
            ref = rest.split(":", 1)[0]
        elif kind == "node":
            ref = rest
        elif kind == "profile":
            row = store.query_one(
                "SELECT id FROM personal_flags WHERE owner = ? AND holder = 'steward'", (rest,)
            )
            if row is None:
                raise FlagError("not_found", "that flag is not on the sheet")
            ref = row["id"]
    row = store.query_one("SELECT * FROM personal_flags WHERE id = ?", (ref,))
    if row is not None:
        return {
            "id": row["id"], "owner": row["owner"], "name": row["display_name"],
            "active": row["status"] == "active",
            "offered": bool(row["offer_title"] or loads(row["intents"])),
        }
    row = store.query_one("SELECT * FROM business_nodes WHERE id = ?", (ref,))
    if row is not None:
        has_flags = store.query_one(
            "SELECT 1 FROM business_flags WHERE node_id = ? AND status = 'active'", (row["id"],)
        )
        return {
            "id": row["id"], "owner": row["controller"], "name": row["name"],
            "active": row["status"] == "active",
            "offered": bool(loads(row["intents"]) or has_flags),
        }
    row = store.query_one(
        """
        SELECT f.id, f.status, n.controller, n.name, n.status AS node_status
          FROM business_flags f JOIN business_nodes n ON n.id = f.node_id
         WHERE f.id = ?
        """,
        (ref,),
    )
    if row is not None:
        return {
            "id": row["id"], "owner": row["controller"], "name": row["name"],
            "active": row["status"] == "active" and row["node_status"] == "active",
            "offered": True,
        }
    raise FlagError("not_found", "that flag is not on the sheet")


def introduce(
    store: FlagStore,
    *,
    actor: str,
    sentence: str,
    flag_id: str = "",
    relay: str = "",
    chat: Any = None,
) -> dict[str, Any]:
    """Tell the other Steward and open a private room for the two of them."""
    from shadenet.chat import STEWARD_PSEUDONYM, create_private_room, get_pseudonym_for_user

    buyer = check_actor(actor)
    target = _target(store, relay or flag_id)
    if not target["active"]:
        raise FlagError("not_found", "that flag is not on the sheet")
    if target["owner"] == buyer:
        raise FlagError("schema_invalid", "that flag is already yours")
    if not target["offered"]:
        raise FlagError("schema_invalid", "they haven't put anything up")
    about = one_sentence(sentence)
    told = about if about[-1] in ".!?" else f"{about}."
    conn = _require_chat(chat)
    room = create_private_room(
        conn,
        name=target["name"],
        topic=about,
        members=[
            STEWARD_PSEUDONYM,
            get_pseudonym_for_user(conn, buyer),
            get_pseudonym_for_user(conn, target["owner"]),
        ],
        opening=(
            f"I told their steward. {target['name']} is in this room. "
            f"You wanted to talk about {told} This room is private."
        ),
    )
    intro_id = new_id("int")
    store.execute(
        """
        INSERT INTO introductions (id, room_id, buyer, seller, seller_flag_id, sentence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (intro_id, room["room_id"], buyer, target["owner"], target["id"], about, now_iso()),
    )
    return {
        "id": intro_id,
        "room_id": room["room_id"],
        "sentence": about,
        "name": target["name"],
        "reply": "I told their steward. The room is private. You are both in it.",
    }


def _room(store: FlagStore, who: str, room_id: str = "", flag_id: str = ""):
    """The introduction a call is about. A seller with several rooms names one."""
    if room_id:
        row = store.query_one("SELECT * FROM introductions WHERE room_id = ?", (room_id,))
        if row is None or who not in (row["buyer"], row["seller"]):
            raise FlagError("not_found", "you're not in that room")
        return row
    if not flag_id:
        raise FlagError("schema_invalid", "name the room")
    target = _target(store, flag_id)
    rows = store.query_all(
        """
        SELECT * FROM introductions
         WHERE seller_flag_id = ? AND (buyer = ? OR seller = ?)
         ORDER BY created_at DESC
        """,
        (target["id"], who, who),
    )
    if not rows:
        raise FlagError("schema_invalid", "open a private room before you call an accord")
    if who == target["owner"] and len({row["buyer"] for row in rows}) > 1:
        raise FlagError("schema_invalid", "more than one person is talking to you about that flag. Name the room.")
    return rows[0]


def _terms_code(room_id: str, version: int, item: str, amount: str, unit: str) -> str:
    return hashlib.sha256(f"{room_id}|{version}|{item}|{amount}|{unit}".encode()).hexdigest()[:16]


def _price(row) -> str:
    return f"{row['amount']} {row['unit']}".strip()


def _view(row, who: str) -> dict[str, Any]:
    side = "buyer" if who == row["buyer"] else "seller"
    other = "seller" if side == "buyer" else "buyer"
    return {
        "id": row["id"],
        "room_id": row["room_id"],
        "side": side,
        "state": row["state"],
        "item": row["item"],
        "amount": row["amount"],
        "unit": row["unit"],
        "terms": row["terms"],
        "you_confirmed": bool(row[f"{side}_confirmed"]),
        "they_confirmed": bool(row[f"{other}_confirmed"]),
        "you_rated": bool(row[f"{side}_rated"]),
    }


def read_accord(
    store: FlagStore,
    *,
    actor: str,
    room_id: str = "",
    flag_id: str = "",
    chat: Any = None,
) -> dict[str, Any]:
    """Read the room once and write down the item and the price."""
    from shadenet.chat import STEWARD_PSEUDONYM, get_pseudonym_for_user, get_room_messages

    who = check_actor(actor)
    intro = _room(store, who, room_id, flag_id)
    conn = _require_chat(chat)
    messages = get_room_messages(conn, intro["room_id"], limit=5000, viewer=STEWARD_PSEUDONYM)
    terms = read_terms(
        messages,
        buyer=get_pseudonym_for_user(conn, intro["buyer"]),
        seller=get_pseudonym_for_user(conn, intro["seller"]),
    )
    stamp = now_iso()
    with store.transaction():
        if store.query_one(
            "SELECT 1 FROM room_obligations WHERE room_id = ? AND state != 'released'", (intro["room_id"],)
        ):
            raise FlagError("schema_invalid", "there is an open obligation on these terms; finish it first")
        row = store.query_one("SELECT * FROM room_accords WHERE room_id = ?", (intro["room_id"],))
        version = (row["version"] if row else 0) + 1
        code = _terms_code(intro["room_id"], version, terms["item"], terms["amount"], terms["unit"])
        if row is None:
            store.execute(
                """
                INSERT INTO room_accords (
                    id, room_id, buyer, seller, item, amount, unit, terms, version,
                    state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'read', ?, ?)
                """,
                (new_id("acd"), intro["room_id"], intro["buyer"], intro["seller"],
                 terms["item"], terms["amount"], terms["unit"], code, version, stamp, stamp),
            )
        else:
            store.execute(
                """
                UPDATE room_accords SET
                    item = ?, amount = ?, unit = ?, terms = ?, version = ?,
                    buyer_confirmed = 0, seller_confirmed = 0,
                    buyer_rated = 0, seller_rated = 0,
                    state = 'read', updated_at = ?
                 WHERE id = ?
                """,
                (terms["item"], terms["amount"], terms["unit"], code, version, stamp, row["id"]),
            )
        saved = store.query_one("SELECT * FROM room_accords WHERE room_id = ?", (intro["room_id"],))
    view = _view(saved, who)
    view["reply"] = (
        f"I read the room. {saved['item']}. The price is {_price(saved)}. "
        "Confirm that this is what you expect."
    )
    return view


def confirm_accord(
    store: FlagStore,
    *,
    actor: str,
    terms: str,
    room_id: str = "",
    flag_id: str = "",
) -> dict[str, Any]:
    """Confirm the exact terms you were shown. Both confirmations make an accord."""
    who = check_actor(actor)
    intro = _room(store, who, room_id, flag_id)
    side = "buyer" if who == intro["buyer"] else "seller"
    with store.transaction():
        row = store.query_one("SELECT * FROM room_accords WHERE room_id = ?", (intro["room_id"],))
        if row is None:
            raise FlagError("schema_invalid", "I haven't read the room yet")
        if not terms or terms != row["terms"]:
            raise FlagError("stale_terms", "Those aren't the terms I read last. Look again before you confirm.")
        store.execute(
            f"UPDATE room_accords SET {side}_confirmed = 1, updated_at = ? WHERE id = ? AND terms = ?",
            (now_iso(), row["id"], terms),
        )
        store.execute(
            """
            UPDATE room_accords SET state = 'accorded'
             WHERE id = ? AND terms = ? AND buyer_confirmed = 1 AND seller_confirmed = 1
            """,
            (row["id"], terms),
        )
        saved = store.query_one("SELECT * FROM room_accords WHERE id = ?", (row["id"],))
    view = _view(saved, who)
    if saved["state"] == "accorded":
        tail = "The buyer can take on the obligation." if saved["unit"].upper() in ("XMR", "MONERO") \
            else "The rest is between you."
        view["reply"] = f"Both of you confirmed. {saved['item']}. The price is {_price(saved)}. {tail}"
    else:
        view["reply"] = f"You confirmed. {saved['item']}. The price is {_price(saved)}. Their user has not confirmed yet."
    return view


def _score(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise FlagError("schema_invalid", "a rating needs hearts, flames, and one word")
    try:
        number = int(value)
    except ValueError:
        raise FlagError("schema_invalid", f"{label} is a number from 1 to 100") from None
    if str(value).strip() != str(number) or not 1 <= number <= 100:
        raise FlagError("schema_invalid", f"{label} is a number from 1 to 100")
    return number


def rate(
    store: FlagStore,
    *,
    actor: str,
    personal: Any,
    product: Any,
    word: Any,
    room_id: str = "",
    flag_id: str = "",
) -> dict[str, Any]:
    """Hearts for the person, flames for the thing, and one word. Once per accord."""
    who = check_actor(actor)
    token = str(word or "").strip()
    if personal in (None, "") or product in (None, "") or not token:
        raise FlagError("schema_invalid", "a rating needs hearts, flames, and one word")
    if not WORD.match(token):
        raise FlagError("schema_invalid", "the word is one word")
    hearts = _score(personal, "the personal rating")
    flames = _score(product, "the product rating")
    intro = _room(store, who, room_id, flag_id)
    side = "buyer" if who == intro["buyer"] else "seller"
    ratee = intro["seller"] if side == "buyer" else intro["buyer"]
    with store.transaction():
        claimed = store.execute(
            f"""
            UPDATE room_accords SET {side}_rated = 1
             WHERE room_id = ? AND state = 'accorded' AND {side}_rated = 0
            """,
            (intro["room_id"],),
        )
        if claimed.rowcount != 1:
            row = store.query_one("SELECT state FROM room_accords WHERE room_id = ?", (intro["room_id"],))
            if row is None or row["state"] != "accorded":
                raise FlagError("schema_invalid", "rate it after both of you confirm")
            raise FlagError("schema_invalid", "you already rated this one")
        store.execute(
            "INSERT INTO ratings (id, ratee, hearts, flames, word, day) VALUES (?, ?, ?, ?, ?, ?)",
            (new_id("rat"), ratee, hearts, flames, token.lower(),
             datetime.now(timezone.utc).date().isoformat()),
        )
    return {"reply": f"Noted. The ratings stay with me until {SAMPLE} of them."}


def counsel(store: FlagStore, *, actor: str) -> dict[str, Any]:
    """Speak about ratings only after a real sample. The sheet never hears this."""
    who = check_actor(actor)
    rows = store.query_all("SELECT hearts, flames, word FROM ratings WHERE ratee = ?", (who,))
    count = len(rows)
    if count < SAMPLE:
        return {
            "ready": False,
            "count": count,
            "note": f"I'm holding the ratings. {SAMPLE} of them, then I will say what to change.",
        }
    personal = sum(row["hearts"] for row in rows) / count
    product = sum(row["flames"] for row in rows) / count
    words = [row["word"] for row in rows]
    word = max(set(words), key=words.count)
    notes: list[str] = []
    if personal < 50:
        notes.append(f"People are rating you low. The word that keeps showing up is {word}.")
    elif personal >= 80:
        notes.append("People are fine with you. Don't sand off the edges.")
    if product < 50:
        notes.append("The thing you are offering is the weak part. Look at that before the small talk.")
    elif product >= 80:
        notes.append("The offer is landing. Leave it alone.")
    if not notes:
        notes.append("You are in the middle of the range. One sharp change will show up faster than a new motto.")
    return {"ready": True, "count": count, "note": " ".join(notes)}
