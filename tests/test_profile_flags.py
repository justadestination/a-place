"""Personal flags and the business flag/node (shadenet.serendipilyst)."""

import sqlite3

import pytest

from shadenet.serendipilyst import (
    FlagError,
    FlagStore,
    anchor_business_flag,
    apply_upsert,
    exposures,
    list_personal_flags,
    map_pins,
    open_personal_flags,
    retract_personal_flag,
    upsert_business_node,
    upsert_personal_flag,
)
from shadenet.serendipilyst.flash import apply_order, clean_appearance
from shadenet.serendipilyst import use_store
from shadenet.steward.command_engine import execute, make_envelope


PERSON = "a2a://agent/personal_lumen"
ROOM = "a2a://agent/venue_neon"
OTHER = "a2a://agent/personal_other"


@pytest.fixture
def store(tmp_path):
    db = FlagStore(tmp_path / "flags.db")
    yield db
    db.close()


def test_human_and_steward_each_get_a_flag(store):
    opened = open_personal_flags(
        store,
        actor=PERSON,
        human={
            "display_name": "Lumen",
            "bio": "At the door.",
            "declarations": ["No recordings."],
        },
        steward={
            "display_name": "Door Steward",
            "skills": ["#SoundTech", "bartender"],
            "availability": ["Weekends 17:00-21:00"],
        },
    )
    human = opened["human"]
    steward = opened["steward"]
    assert human["id"].startswith("flg_")
    assert steward["id"].startswith("flg_")
    assert human["id"] != steward["id"]
    assert human["holder"] == "human"
    assert steward["holder"] == "steward"
    assert human["owner"] == steward["owner"] == PERSON
    assert human["address"] == ""
    assert steward["address"].startswith("a2a://relay/")
    assert human["linked_flag_id"] == steward["id"]
    assert steward["linked_flag_id"] == human["id"]
    assert human["display_name"] == "Lumen"
    assert steward["display_name"] == "Door Steward"
    assert steward["skills"] == ["soundtech", "bartender"]
    assert human["bio"] == "At the door."
    assert steward["bio"] == ""
    assert exposures(store) == []

    upsert_personal_flag(
        store,
        actor=PERSON,
        holder="human",
        display_name="Lumen",
        bio="Still at the door.",
    )
    flags = {flag["holder"]: flag for flag in list_personal_flags(store)}
    assert flags["human"]["bio"] == "Still at the door."
    assert flags["steward"]["display_name"] == "Door Steward"
    assert flags["steward"]["skills"] == ["soundtech", "bartender"]


def test_opening_one_flag_requires_the_other_name(store):
    with pytest.raises(FlagError) as caught:
        upsert_personal_flag(store, actor=PERSON, holder="steward", display_name="Door Steward")
    assert caught.value.code == "schema_invalid"


def test_personal_offer_stays_on_its_own_flag(store):
    opened = open_personal_flags(
        store,
        actor=PERSON,
        human={"displayName": "Lumen"},
        steward={"displayName": "Door Steward"},
    )
    hidden = upsert_personal_flag(
        store,
        actor=PERSON,
        holder="human",
        flag_id=opened["human"]["id"],
        display_name="Lumen",
        offer_title="Tube amp, cash in person",
        offer_body="Working Sansui. Downtown handoff.",
    )
    feed = exposures(store)
    assert len(feed) == 1
    assert feed[0]["holder"] == "human"
    assert feed[0]["title"] == "Tube amp, cash in person"
    assert feed[0]["flag_id"] is None
    assert feed[0]["inbox"].startswith("a2a://relay/")
    assert PERSON not in str(feed)

    linked = upsert_personal_flag(
        store,
        actor=PERSON,
        holder="human",
        flag_id=hidden["id"],
        display_name="Lumen",
        offer_title="Tube amp, cash in person",
        offer_body="Working Sansui. Downtown handoff.",
        link_postings=True,
        anonymous=False,
    )
    assert exposures(store)[0]["flag_id"] == linked["id"]
    assert exposures(store)[0]["anonymous"] is False
    steward = next(flag for flag in list_personal_flags(store) if flag["holder"] == "steward")
    assert steward["offer_title"] == ""


def test_stranger_cannot_edit_either_flag(store):
    opened = open_personal_flags(
        store,
        actor=PERSON,
        human={"display_name": "Lumen"},
        steward={"display_name": "Door Steward"},
    )
    with pytest.raises(FlagError) as caught:
        upsert_personal_flag(
            store,
            actor=OTHER,
            holder="human",
            flag_id=opened["human"]["id"],
            display_name="Not Lumen",
        )
    assert caught.value.code == "scope_denied"


def test_retract_drops_one_flag_and_leaves_the_other(store):
    opened = open_personal_flags(
        store,
        actor=PERSON,
        human={
            "display_name": "Lumen",
            "offer_title": "Patch cables",
            "offer_body": "A handful, cash only.",
        },
        steward={"display_name": "Door Steward"},
    )
    retract_personal_flag(store, actor=PERSON, flag_id=opened["human"]["id"])
    assert exposures(store) == []
    remaining = list_personal_flags(store)
    assert [flag["holder"] for flag in remaining] == ["steward"]


def test_offer_needs_title_and_body(store):
    open_personal_flags(
        store,
        actor=PERSON,
        human={"display_name": "Lumen"},
        steward={"display_name": "Door Steward"},
    )
    with pytest.raises(FlagError) as caught:
        upsert_personal_flag(
            store,
            actor=PERSON,
            holder="human",
            display_name="Lumen",
            offer_title="Amp",
        )
    assert caught.value.code == "schema_invalid"


def test_business_node_then_flag(store):
    node = upsert_business_node(
        store,
        actor=ROOM,
        name="The Neon Foundry",
        venue_id="ven_neon",
    )
    assert node["id"].startswith("biz_")
    assert node["inbox"].startswith("a2a://relay/")
    assert node["controller"] == ROOM
    assert node["kind"] == "business_node"

    again = upsert_business_node(store, actor=ROOM, name="The Neon Foundry")
    assert again["id"] == node["id"]

    flag = anchor_business_flag(
        store,
        actor=ROOM,
        node_id=node["id"],
        title="Backline for Sunday",
        body="Bass amp on the patio. Cash at the door.",
        skills=["backline"],
    )
    assert flag["node_id"] == node["id"]
    assert flag["node_name"] == "The Neon Foundry"
    feed = exposures(store)
    assert len(feed) == 1
    assert feed[0]["kind"] == "business"
    assert feed[0]["inbox"] == node["inbox"]
    assert ROOM not in str(feed)
    assert feed[0]["anonymous"] is True


def test_flag_requires_the_node_inbox(store):
    node = upsert_business_node(store, actor=ROOM, name="The Neon Foundry")
    with pytest.raises(FlagError) as missing:
        anchor_business_flag(
            store, actor=ROOM, node_id="biz_missing", title="Amp", body="Cash.",
        )
    assert missing.value.code == "not_found"
    with pytest.raises(FlagError) as denied:
        anchor_business_flag(
            store, actor=OTHER, node_id=node["id"], title="Amp", body="Cash.",
        )
    assert denied.value.code == "scope_denied"


def test_upsert_rejects_payment_fields(store):
    result = apply_upsert(
        {"kind": "personal", "actor": PERSON, "display_name": "Lumen", "price": "40"},
        store=store,
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "schema_invalid"


def test_command_engine_flags_upsert_roundtrip(store):
    use_store(store)
    sender = ROOM
    node = execute(
        make_envelope(
            "flags.upsert",
            {"kind": "business_node", "name": "The Neon Foundry", "venueId": "ven_neon"},
            sender,
        ),
        sender,
    )
    assert node["ok"] is True
    flag = execute(
        make_envelope(
            "flags.upsert",
            {
                "kind": "business_flag",
                "nodeId": node["result"]["id"],
                "title": "Monday load-in",
                "body": "Two hands, cash at the end of the night.",
            },
            sender,
        ),
        sender,
    )
    assert flag["ok"] is True
    assert exposures(store)[0]["title"] == "Monday load-in"

    stranger = execute(
        make_envelope("flags.upsert", {"kind": "personal", "displayName": "Nope"}, "not-an-agent"),
        "not-an-agent",
    )
    assert stranger["ok"] is False
    assert stranger["error"]["code"] == "scope_denied"
    use_store(None)


def test_listed_flag_publishes_its_place(store):
    use_store(store)
    opened = execute(
        make_envelope(
            "flags.upsert",
            {
                "kind": "personal",
                "human": {
                    "displayName": "Lumen",
                    "listed": True,
                    "place_id": "square",
                    "appearance": {"field": "crimson", "charge": "dagger", "motto": "TUBE AMP"},
                },
                "steward": {
                    "displayName": "Door Steward",
                    "place_id": "square",
                    "appearance": {"field": "gold", "charge": "acorn", "motto": "DOOR"},
                },
            },
            PERSON,
        ),
        PERSON,
    )
    assert opened["ok"] is True
    pins = map_pins(store)
    assert len(pins) == 1
    assert pins[0]["holder"] == "human"
    assert pins[0]["name"] == "Lumen"
    assert pins[0]["place_id"] == "square"
    assert pins[0]["appearance"] == {"field": "crimson", "charge": "dagger", "motto": "TUBE AMP"}
    assert "owner" not in pins[0]
    flags = {flag["holder"]: flag for flag in list_personal_flags(store)}
    assert flags["steward"]["listed"] is False
    assert flags["steward"]["place_id"] == "square"
    assert flags["steward"]["place_id"] not in [pin["place_id"] for pin in pins if pin["holder"] == "steward"]

    node = upsert_business_node(
        store,
        actor=ROOM,
        name="The Neon Foundry",
        listed=True,
        place_id="rail",
        appearance={"field": "rust", "charge": "anchor", "motto": "SUNDAY"},
    )
    business = [pin for pin in map_pins(store) if pin["kind"] == "business_node"]
    assert business == [{
        "id": node["id"],
        "kind": "business_node",
        "name": "The Neon Foundry",
        "place_id": "rail",
        "appearance": {"field": "rust", "charge": "anchor", "motto": "SUNDAY"},
        "inbox": node["inbox"],
    }]
    use_store(None)


def test_unlisted_place_stays_off_the_map(store):
    open_personal_flags(
        store,
        actor=PERSON,
        human={"display_name": "Lumen", "listed": False, "place_id": "lot"},
        steward={"display_name": "Door Steward"},
    )
    assert map_pins(store) == []
    flags = {flag["holder"]: flag for flag in list_personal_flags(store)}
    assert flags["human"]["place_id"] == "lot"
    assert flags["human"]["listed"] is False


def test_listing_requires_a_known_place(store):
    with pytest.raises(FlagError) as missing:
        open_personal_flags(
            store,
            actor=PERSON,
            human={"display_name": "Lumen", "listed": True},
            steward={"display_name": "Door Steward"},
        )
    assert missing.value.code == "schema_invalid"
    with pytest.raises(FlagError) as unknown:
        upsert_personal_flag(
            store,
            actor=PERSON,
            holder="human",
            display_name="Lumen",
            counterpart_name="Door Steward",
            listed=True,
            place_id="not-a-place",
        )
    assert unknown.value.code == "schema_invalid"


def test_appearance_rejects_unknown_charge_and_a_long_motto(store):
    with pytest.raises(FlagError) as charge:
        open_personal_flags(
            store,
            actor=PERSON,
            human={
                "display_name": "Lumen",
                "appearance": {"field": "crimson", "charge": "skull", "motto": "NO"},
            },
            steward={"display_name": "Door Steward"},
        )
    assert charge.value.code == "schema_invalid"
    with pytest.raises(FlagError) as motto:
        open_personal_flags(
            store,
            actor=PERSON,
            human={"display_name": "Lumen", "appearance": {"motto": "X" * 25}},
            steward={"display_name": "Door Steward"},
        )
    assert motto.value.code == "schema_invalid"
    rejected = execute(
        make_envelope(
            "flags.upsert",
            {
                "kind": "personal",
                "holder": "human",
                "displayName": "Lumen",
                "counterpartName": "Door Steward",
                "appearance": {"field": "crimson", "charge": "dagger", "glow": True},
            },
            PERSON,
        ),
        PERSON,
    )
    assert rejected["ok"] is False
    assert rejected["error"]["code"] == "schema_invalid"


def test_old_flag_table_gains_listing_columns(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE personal_flags (
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
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()
    store = FlagStore(path)
    names = {row["name"] for row in store.query_all("PRAGMA table_info(personal_flags)")}
    assert {"listed", "place_id", "appearance"} <= names
    opened = open_personal_flags(
        store,
        actor=PERSON,
        human={"display_name": "Lumen", "listed": True, "place_id": "lot"},
        steward={"display_name": "Door Steward"},
    )
    assert opened["human"]["listed"] is True
    assert map_pins(store)[0]["place_id"] == "lot"
    store.close()


def test_paint_it_black_changes_only_the_field():
    base = {"field": "crimson", "charge": "dagger", "motto": "TUBE AMP"}
    heard = apply_order("paint it black", base)
    assert heard["appearance"] == {"field": "ink", "charge": "dagger", "motto": "TUBE AMP"}
    assert heard["listed"] is None
    assert heard["place_id"] is None
    assert heard["reply"] == "Painted black."
    dagger = apply_order("dagger", {"field": "gold", "charge": "none", "motto": ""})
    assert dagger["appearance"] == {"field": "gold", "charge": "dagger", "motto": ""}
    rose = apply_order("dagger and rose")
    assert rose["appearance"]["charge"] == "dagger"
    motto = apply_order("motto KEEP IT", base)
    assert motto["appearance"]["motto"] == "KEEP IT"
    assert motto["appearance"]["field"] == "crimson"


def test_order_can_list_pull_and_cut_the_cloth():
    listed = apply_order(
        "paint it black and list it at the lot",
        {"field": "crimson", "charge": "dagger", "motto": "TUBE AMP"},
    )
    assert listed["appearance"]["field"] == "ink"
    assert listed["appearance"]["charge"] == "dagger"
    assert listed["listed"] is True
    assert listed["place_id"] == "lot"
    assert "Listed at The Lot." in listed["reply"]
    pulled = apply_order("pull it", listed["appearance"])
    assert pulled["listed"] is False
    assert pulled["appearance"]["field"] == "ink"
    assert pulled["appearance"]["charge"] == "dagger"
    cut = apply_order("fine line, no ribbon, notched", listed["appearance"])
    assert cut["appearance"]["line"] == "fine"
    assert cut["appearance"]["ribbon"] is False
    assert cut["appearance"]["fly"] == "notched"
    assert cut["appearance"]["motto"] == "TUBE AMP"
    square = apply_order("list it at courthouse square")
    assert square["place_id"] == "square"
    assert "fly" not in square["appearance"]


def test_unknown_order_and_bad_cloth_are_refused():
    with pytest.raises(FlagError) as unknown:
        apply_order("make it plaid", {"field": "crimson", "charge": "dagger", "motto": "X"})
    assert unknown.value.code == "schema_invalid"
    with pytest.raises(FlagError):
        apply_order("motto " + ("X" * 25))
    with pytest.raises(FlagError):
        clean_appearance({"field": "ink", "line": "plaid"})
    with pytest.raises(FlagError):
        clean_appearance({"fly": "square"})


def test_order_merges_onto_the_listed_flag(store):
    use_store(store)
    opened = execute(
        make_envelope(
            "flags.upsert",
            {
                "kind": "personal",
                "holder": "human",
                "displayName": "Lumen",
                "counterpartName": "Door Steward",
                "listed": True,
                "placeId": "square",
                "appearance": {"field": "crimson", "charge": "dagger", "motto": "TUBE AMP"},
            },
            PERSON,
        ),
        PERSON,
    )
    assert opened["ok"] is True
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
    assert painted["result"]["listed"] is True
    assert painted["result"]["place_id"] == "square"
    assert painted["result"]["appearance"] == {
        "field": "ink",
        "charge": "dagger",
        "motto": "TUBE AMP",
    }
    moved = execute(
        make_envelope(
            "flags.upsert",
            {
                "kind": "personal",
                "holder": "human",
                "displayName": "Lumen",
                "order": "list it at the lot",
            },
            PERSON,
        ),
        PERSON,
    )
    assert moved["ok"] is True
    human = [pin for pin in map_pins(store) if pin.get("holder") == "human"]
    assert human[0]["place_id"] == "lot"
    assert human[0]["appearance"]["field"] == "ink"
    assert human[0]["appearance"]["charge"] == "dagger"
    missed = execute(
        make_envelope(
            "flags.upsert",
            {
                "kind": "personal",
                "holder": "human",
                "displayName": "Lumen",
                "order": "make it plaid",
            },
            PERSON,
        ),
        PERSON,
    )
    assert missed["ok"] is False
    assert missed["error"]["code"] == "schema_invalid"
    assert map_pins(store)[0]["appearance"]["charge"] == "dagger"
    node = execute(
        make_envelope(
            "flags.upsert",
            {
                "kind": "business_node",
                "name": "The Neon Foundry",
                "listed": True,
                "placeId": "rail",
                "appearance": {"field": "rust", "charge": "anchor", "motto": "SUNDAY"},
            },
            ROOM,
        ),
        ROOM,
    )
    assert node["ok"] is True
    node_paint = execute(
        make_envelope(
            "flags.upsert",
            {"kind": "business_node", "name": "The Neon Foundry", "order": "paint it black"},
            ROOM,
        ),
        ROOM,
    )
    assert node_paint["ok"] is True
    assert node_paint["result"]["listed"] is True
    assert node_paint["result"]["place_id"] == "rail"
    assert node_paint["result"]["appearance"]["field"] == "ink"
    assert node_paint["result"]["appearance"]["charge"] == "anchor"
    bad_line = execute(
        make_envelope(
            "flags.upsert",
            {
                "kind": "personal",
                "holder": "human",
                "displayName": "Lumen",
                "appearance": {"line": "plaid"},
            },
            PERSON,
        ),
        PERSON,
    )
    assert bad_line["ok"] is False
    assert bad_line["error"]["code"] == "schema_invalid"
    use_store(None)
