"""Intent marks, the private room, and the Monero obligation."""

import json
import sqlite3

import pytest

from shadenet.chat import (
    DOMAIN,
    STEWARD_PSEUDONYM,
    get_pseudonym_for_user,
    get_room_messages,
    init_chat_schema,
    list_rooms,
    post_message,
)
from shadenet.serendipilyst import (
    FlagError,
    FlagStore,
    counsel,
    map_pins,
    open_personal_flags,
    use_chat,
    use_store,
)
from shadenet.serendipilyst.flash import apply_order
from shadenet.serendipilyst.intents import use_reader
from shadenet.steward.command_engine import execute, make_envelope


PERSON = "a2a://agent/personal_lumen"
OTHER = "a2a://agent/personal_other"


@pytest.fixture
def store(tmp_path):
    db = FlagStore(tmp_path / "flags.db")
    yield db
    db.close()
    use_store(None)
    use_chat(None)
    use_reader(None)


def _chat():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_chat_schema(conn)
    return conn


def test_an_intent_needs_a_sentence():
    with pytest.raises(FlagError, match="sentence"):
        apply_order("looking for a conversation")


def test_paint_it_black_keeps_the_intent_and_the_dagger(store):
    use_store(store)
    opened = open_personal_flags(
        store,
        actor=PERSON,
        human={
            "display_name": "Lumen",
            "listed": True,
            "place_id": "square",
            "appearance": {"field": "crimson", "charge": "dagger", "motto": "TUBE AMP"},
            "order": "looking for a conversation about the square",
        },
        steward={"display_name": "Door Steward"},
    )
    human = opened["human"]
    assert human["appearance"]["charge"] == "dagger"
    assert human["appearance"]["field"] == "crimson"
    assert human["place_id"] == "square"
    assert human["intents"] == [{
        "kind": "conversation",
        "sentence": "the square",
    }]
    painted = execute(
        make_envelope(
            "flags.upsert",
            {
                "kind": "personal",
                "holder": "human",
                "displayName": "Lumen",
                "order": "paint it black",
            },
            PERSON,
        ),
        PERSON,
    )
    assert painted["ok"] is True
    assert painted["result"]["appearance"] == {
        "field": "ink",
        "charge": "dagger",
        "motto": "TUBE AMP",
    }
    assert painted["result"]["intents"] == human["intents"]
    assert painted["result"]["listed"] is True


def test_interest_opens_a_private_room_and_refuses_an_empty_flag(store):
    use_store(store)
    chat = _chat()
    use_chat(chat)
    bare = open_personal_flags(
        store,
        actor=PERSON,
        human={"display_name": "Lumen"},
        steward={"display_name": "Door Steward"},
    )
    refused = execute(
        make_envelope(
            "flags.deal",
            {"action": "interest", "flag_id": bare["human"]["id"], "sentence": "The amp."},
            OTHER,
        ),
        OTHER,
    )
    assert refused["ok"] is False
    assert "haven't put anything up" in refused["error"]["message"]

    offered = execute(
        make_envelope(
            "flags.upsert",
            {
                "kind": "personal",
                "holder": "human",
                "displayName": "Lumen",
                "order": "looking for a conversation about the tube amp",
            },
            PERSON,
        ),
        PERSON,
    )
    assert offered["ok"] is True
    told = execute(
        make_envelope(
            "flags.deal",
            {
                "action": "interest",
                "flag_id": bare["human"]["id"],
                "sentence": "I want to hear that amp.",
            },
            OTHER,
        ),
        OTHER,
    )
    assert told["ok"] is True
    assert told["result"]["reply"] == "I told their steward. The room is private. You are both in it."
    room_id = told["result"]["room_id"]
    assert all(room["room_id"] != room_id for room in list_rooms(chat))
    buyer = get_pseudonym_for_user(chat, OTHER)
    seller = get_pseudonym_for_user(chat, PERSON)
    messages = get_room_messages(chat, room_id, viewer=buyer)
    assert messages[0]["sender"] == STEWARD_PSEUDONYM
    assert seller.startswith("@anon-") and seller.endswith(f":{DOMAIN}")
    with pytest.raises(PermissionError):
        get_room_messages(chat, room_id)
    chat.close()


def _deal(action, sender, **fields):
    return execute(make_envelope("flags.deal", {"action": action, **fields}, sender), sender)


def _read(sender, flag_id):
    return _deal("accord", sender, flag_id=flag_id, step="read")


def test_obligation_ratings_stay_off_the_map_until_the_sample(store):
    use_store(store)
    chat = _chat()
    use_chat(chat)
    try:
        opened = open_personal_flags(
            store,
            actor=PERSON,
            human={
                "display_name": "Lumen",
                "listed": True,
                "place_id": "square",
                "appearance": {"field": "crimson", "charge": "dagger", "motto": "TUBE AMP"},
                "order": "stuff for sale: Sunday backline, one night.",
            },
            steward={"display_name": "Door Steward"},
        )
        flag_id = opened["human"]["id"]
        thing = "Sunday backline, one night."
        early = _deal("oblige", OTHER, flag_id=flag_id, sentence=thing, amount="1.5")
        assert early["ok"] is False
        assert "confirm" in early["error"]["message"]
        assert "price" in early["error"]["message"]

        told = _deal("interest", OTHER, flag_id=flag_id, sentence=thing)
        assert told["ok"] is True
        room_id = told["result"]["room_id"]
        buyer = get_pseudonym_for_user(chat, OTHER)
        seller = get_pseudonym_for_user(chat, PERSON)
        calls: list[str] = []
        seller_reads = {"n": 0}

        def complete(prompt: str) -> str:
            calls.append(prompt)
            assert "a2a://" not in prompt
            assert "I will take Sunday." in prompt
            assert "Sunday is yours for that price." in prompt
            if "buyer's steward" in prompt:
                amount = "1.5 XMR"
            else:
                seller_reads["n"] += 1
                amount = "2" if seller_reads["n"] == 1 else "1.50"
            body = {
                "buyer_give": "the night",
                "buyer_get": thing,
                "seller_give": thing,
                "seller_get": "the night",
                "amount": amount,
            }
            return "```json\n" + json.dumps(body) + "\n```"

        use_reader(complete)
        quiet = _read(OTHER, flag_id)
        assert quiet["ok"] is False
        assert "speak" in quiet["error"]["message"]
        assert calls == []
        post_message(chat, room_id, buyer, "I will take Sunday.")
        still = _read(OTHER, flag_id)
        assert still["ok"] is False
        assert "speak" in still["error"]["message"]
        assert calls == []
        post_message(chat, room_id, seller, "Sunday is yours for that price.")

        handed = _deal("accord", OTHER, flag_id=flag_id, step="read", amount="9")
        assert handed["ok"] is False
        assert "Don't hand me the price" in handed["error"]["message"]
        assert calls == []
        use_reader(lambda prompt: "not json")
        garbled = _read(OTHER, flag_id)
        assert garbled["ok"] is False
        assert "cannot tell" in garbled["error"]["message"]
        use_reader(lambda prompt: json.dumps({"unclear": True}))
        unsure = _read(OTHER, flag_id)
        assert unsure["ok"] is False
        assert "cannot tell" in unsure["error"]["message"]
        use_reader(complete)

        buyer_read = _read(OTHER, flag_id)
        assert buyer_read["ok"] is True
        assert "buyer's steward" in calls[0]
        assert buyer_read["result"]["state"] == "reading"
        assert "not read it back" in buyer_read["result"]["reply"]
        assert "You give the night." in buyer_read["result"]["reply"]
        assert "They give Sunday backline, one night." in buyer_read["result"]["reply"]
        assert "The price is 1.5 XMR" in buyer_read["result"]["reply"]

        apart = _read(PERSON, flag_id)
        assert apart["ok"] is True
        assert apart["result"]["state"] == "apart"
        assert "not on the same page" in apart["result"]["reply"]
        assert "Nothing is confirmed" in apart["result"]["reply"]
        refused = _deal("accord", PERSON, flag_id=flag_id, step="confirm")
        assert refused["ok"] is False
        assert "not on the same page" in refused["error"]["message"]

        aligned = _read(PERSON, flag_id)
        assert aligned["ok"] is True
        assert aligned["result"]["state"] == "agreed"
        reply = aligned["result"]["reply"]
        assert "same page" in reply
        assert "You give Sunday backline, one night." in reply
        assert "You get the night." in reply
        assert "They give the night." in reply
        assert "They get Sunday backline, one night." in reply
        assert "The price is 1.5 XMR" in reply

        yours = _deal("accord", OTHER, flag_id=flag_id, step="confirm")
        assert yours["ok"] is True
        assert "Their user has not confirmed yet" in yours["result"]["reply"]
        assert yours["result"]["state"] == "agreed"
        waiting = _deal("oblige", OTHER, flag_id=flag_id, sentence=thing, amount="1.5")
        assert waiting["ok"] is False

        theirs = _deal("accord", PERSON, flag_id=flag_id, step="confirm")
        assert theirs["ok"] is True
        assert theirs["result"]["state"] == "accorded"
        assert "Both of you confirmed" in theirs["result"]["reply"]

        wrong_room = _deal(
            "oblige", OTHER, flag_id=flag_id, sentence=thing, amount="1.5",
            room_id="!private_nope:shady.example.org",
        )
        assert wrong_room["ok"] is False
        assert "room" in wrong_room["error"]["message"]
        wrong_thing = _deal("oblige", OTHER, flag_id=flag_id, sentence="A different night.", amount="1.5")
        assert wrong_thing["ok"] is False
        assert "price" in wrong_thing["error"]["message"]

        obliged = _deal("oblige", OTHER, flag_id=flag_id, sentence=thing, amount="1.5")
        assert obliged["ok"] is True
        obligation_id = obliged["result"]["id"]
        assert obliged["result"]["state"] == "obliged"
        assert obliged["result"]["room_id"] == room_id

        bare = _deal("pay", OTHER, obligation_id=obligation_id, personal=30, product=35)
        assert bare["ok"] is False
        assert "a rating needs hearts, flames, and one word" in bare["error"]["message"]
        bad_word = _deal(
            "pay", OTHER, obligation_id=obligation_id,
            personal=30, product=35, word="not one",
        )
        assert bad_word["ok"] is False
        assert bad_word["error"]["message"] == "the word is one word"
        paid = _deal(
            "pay", OTHER, obligation_id=obligation_id,
            tip="0.1", personal=30, product=35, word="thin",
        )
        assert paid["ok"] is True
        assert paid["result"]["state"] == "paid"
        assert paid["result"]["buyer_personal"] == 30
        assert paid["result"]["buyer_word"] == "thin"
        assert "25" in paid["result"]["reply"]
        partial = _deal("release", PERSON, obligation_id=obligation_id, word="fair")
        assert partial["ok"] is False
        assert "a rating needs hearts, flames, and one word" in partial["error"]["message"]
        released = _deal(
            "release", PERSON, obligation_id=obligation_id,
            personal=80, product=80, word="solid",
        )
        assert released["ok"] is True
        assert released["result"]["state"] == "released"
        pin = map_pins(store)[0]
        dumped = json.dumps(pin)
        assert "owner" not in pin
        assert "1.5" not in dumped
        assert "thin" not in dumped
        assert "heart" not in dumped
        assert "price" not in dumped
        assert pin["intents"][0]["kind"] == "sale"
        held = counsel(store, actor=PERSON)
        assert held["ready"] is False
        assert "holding" in held["note"]

        for _ in range(24):
            again = _read(OTHER, flag_id)
            assert again["ok"] is True
            assert again["result"]["state"] == "reading"
            blocked = _deal("oblige", OTHER, flag_id=flag_id, sentence=thing, amount="1.5")
            assert blocked["ok"] is False
            seller_again = _read(PERSON, flag_id)
            assert seller_again["result"]["state"] == "agreed"
            assert _deal("accord", OTHER, flag_id=flag_id, step="confirm")["ok"] is True
            done_accord = _deal("accord", PERSON, flag_id=flag_id, step="confirm")
            assert done_accord["result"]["state"] == "accorded"
            row = _deal("oblige", OTHER, flag_id=flag_id, sentence=thing, amount="1.5")
            assert row["ok"] is True
            paid_row = _deal(
                "pay", OTHER, obligation_id=row["result"]["id"],
                personal=30, product=30, word="thin",
            )
            assert paid_row["ok"] is True
            done = _deal(
                "release", PERSON, obligation_id=row["result"]["id"],
                personal=80, product=80, word="solid",
            )
            assert done["ok"] is True
        spoken = _deal("counsel", PERSON)
        assert spoken["ok"] is True
        assert spoken["result"]["ready"] is True
        assert spoken["result"]["count"] == 25
        assert "rating you low" in spoken["result"]["note"]
        assert "weak part" in spoken["result"]["note"]
        fresh = json.dumps(map_pins(store)[0])
        assert "thin" not in fresh
        assert "1.5" not in fresh
        assert "price" not in fresh
    finally:
        chat.close()
