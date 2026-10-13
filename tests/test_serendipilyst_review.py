"""Regression tests for the 2026-10-13 Serendipilyst review.

Each test names the review finding it covers.
"""

import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from shadenet import serendipilyst
from shadenet.serendipilyst import (
    FlagError,
    FlagStore,
    anchor_business_flag,
    apply_upsert,
    exposures,
    list_personal_flags,
    map_pins,
    open_personal_flags,
    pending_venues,
    resolve_relay,
    upsert_business_node,
    upsert_personal_flag,
    use_store,
    verify_venue,
)
from shadenet.serendipilyst import policy, reader, web
from shadenet.serendipilyst.fields import leaks, one_sentence
from shadenet.serendipilyst.intents import clean_intents

PERSON = "a2a://agent/personal_lumen"
OTHER = "a2a://agent/personal_other"


@pytest.fixture
def store(tmp_path):
    db = FlagStore(tmp_path / "flags.db")
    yield db
    db.close()
    use_store(None)
    reader.use_reader(None)


def _pair(store, **human):
    return open_personal_flags(
        store, actor=PERSON,
        human={"display_name": "Lumen", **human},
        steward={"display_name": "Door Steward"},
    )


# 1, 2: no public record names the Steward.

def test_an_unlinked_offer_answers_at_a_relay_of_its_own(store):
    _pair(store, offer_title="Amp", offer_body="Bass amp.")
    steward = next(f for f in list_personal_flags(store) if f["holder"] == "steward")
    feed = exposures(store)
    assert feed[0]["flag_id"] is None
    inbox = feed[0]["inbox"]
    assert inbox.startswith("a2a://relay/")
    assert inbox != steward["address"]
    assert resolve_relay(store, inbox)["target"] == PERSON
    assert exposures(store)[0]["inbox"] == inbox
    upsert_personal_flag(store, actor=PERSON, holder="human", offer_title="Kit", offer_body="Drum kit.")
    assert exposures(store)[0]["inbox"] != inbox
    public = json.dumps({"pins": map_pins(store), "offers": exposures(store)})
    assert PERSON not in public


def test_a_venue_is_not_tied_to_its_stewards_profile(store):
    _pair(store)
    node = apply_upsert({"kind": "business_node", "actor": PERSON, "name": "Foundry"}, store)
    assert node["ok"] is True
    assert "controller" not in node["result"]
    steward = next(f for f in list_personal_flags(store) if f["holder"] == "steward")
    assert node["result"]["inbox"] != steward["address"]
    assert PERSON not in json.dumps(node["result"])


# 5: a decimal is not a second sentence.

def test_a_decimal_point_is_not_a_sentence_end():
    assert one_sentence("0.5 XMR") == "0.5 XMR"
    assert one_sentence("A 3.5mm cable.") == "A 3.5mm cable."
    with pytest.raises(FlagError):
        one_sentence("Bass amp. Cash at the door.")


# 9: a write changes only what it names.

def test_a_bio_edit_keeps_marks_listing_and_place(store):
    apply_upsert({
        "kind": "personal", "actor": PERSON, "holder": "human", "display_name": "Al",
        "counterpart_name": "Stew", "order": "selling a bass amp, list it at the square",
        "good_at": "Fixing amps.",
    }, store)
    edited = apply_upsert({"kind": "personal", "actor": PERSON, "holder": "human", "bio": "new bio"}, store)
    assert edited["ok"] is True, edited
    flag = edited["result"]
    assert flag["intents"] == [{"kind": "sale", "sentence": "a bass amp"}]
    assert flag["listed"] is True
    assert flag["place_id"] == "square"
    assert flag["good_at"] == "Fixing amps."
    cleared = apply_upsert({"kind": "personal", "actor": PERSON, "holder": "human", "intents": []}, store)
    assert cleared["result"]["intents"] == []
    assert cleared["result"]["bio"] == "new bio"


def test_intents_and_lines_can_be_set_directly(store):
    result = apply_upsert({
        "kind": "business_node", "actor": PERSON, "name": "Foundry",
        "intents": [{"kind": "sale", "sentence": "Sunday backline, one night."}],
        "enjoy": "Loud rooms.",
    }, store)
    assert result["ok"] is True, result
    again = apply_upsert({"kind": "business_node", "actor": PERSON, "anonymous": False}, store)
    assert again["result"]["intents"][0]["kind"] == "sale"
    assert again["result"]["enjoy"] == "Loud rooms."


# 12: a pair opens whole or not at all.

def test_a_refused_pair_leaves_nothing_behind(store):
    with pytest.raises(FlagError):
        open_personal_flags(store, actor=PERSON, human={"display_name": "Al"},
                            steward={"display_name": "Stew", "skills": ["not a tag!"]})
    assert list_personal_flags(store, active_only=False) == []


def test_concurrent_writers_do_not_trip_over_each_other(store):
    _pair(store)
    errors: list[Exception] = []

    def edit(n: int) -> None:
        try:
            for i in range(20):
                upsert_personal_flag(store, actor=PERSON, holder="human", bio=f"{n}-{i}")
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=edit, args=(n,)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []


# 14: a venue name is a claim until an operator verifies it.

def test_venue_id_stays_off_the_sheet_until_verified(store):
    node = upsert_business_node(store, actor=PERSON, name="Foundry", venue_id="foundry",
                                listed=True, place_id="rail")
    assert "venue_id" not in map_pins(store)[0]
    assert [n["id"] for n in pending_venues(store)] == [node["id"]]
    verify_venue(store, node_id=node["id"])
    assert map_pins(store)[0]["venue_id"] == "foundry"
    moved = upsert_business_node(store, actor=PERSON, venue_id="elsewhere")
    assert moved["venue_verified"] is False
    assert "venue_id" not in map_pins(store)[0]


def test_one_steward_can_run_two_nodes(store):
    first = upsert_business_node(store, actor=PERSON, name="Foundry")
    second = upsert_business_node(store, actor=PERSON, name="Annex", new=True)
    assert first["id"] != second["id"]
    with pytest.raises(FlagError, match="more than one node"):
        upsert_business_node(store, actor=PERSON, name="Which")
    with pytest.raises(FlagError) as denied:
        upsert_business_node(store, actor=OTHER, node_id=first["id"], name="Mine now")
    assert denied.value.code == "scope_denied"


def test_old_nodes_move_the_steward_out_of_the_inbox(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE business_nodes (id TEXT PRIMARY KEY, name TEXT NOT NULL, inbox TEXT NOT NULL UNIQUE,
           venue_id TEXT, anonymous INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'active',
           created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
    )
    conn.execute("INSERT INTO business_nodes VALUES ('biz_1', 'Foundry', ?, NULL, 1, 'active', 'x', 'x')", (PERSON,))
    conn.commit()
    conn.close()
    db = FlagStore(path)
    row = db.query_one("SELECT inbox, controller FROM business_nodes WHERE id = 'biz_1'")
    assert row["controller"] == PERSON
    assert row["inbox"].startswith("a2a://relay/")
    assert resolve_relay(db, row["inbox"])["target"] == PERSON
    db.close()


# 15: an armored public key fits.

def test_an_armored_pgp_key_fits(store):
    key = "-----BEGIN PGP PUBLIC KEY BLOCK-----\n" + ("mQINBF" + "a" * 58 + "\n") * 40 + "-----END PGP PUBLIC KEY BLOCK-----"
    assert len(key) > 2000
    result = apply_upsert({"kind": "personal", "actor": PERSON, "holder": "human",
                           "display_name": "Al", "counterpart_name": "Stew", "pgp": key}, store)
    assert result["ok"] is True, result


# 18: two marks of one kind are refused, not collapsed.

def test_two_marks_of_one_kind_are_refused():
    with pytest.raises(FlagError, match="one mark per intent"):
        clean_intents([{"kind": "sale", "sentence": "Amp."}, {"kind": "sale", "sentence": "Kit."}])


# 19: a long room is trimmed, not refused.

def test_a_long_room_reads_its_last_fifty_lines():
    lines = [{"sender": "@a", "content": f"line {n}"} for n in range(80)]
    lines.append({"sender": "@b", "content": "Deal at 4."})
    said = reader.transcript(lines, {"@a", "@b"})
    assert said.count("\n") == 49
    assert "line 79" in said and "line 10" not in said


# 20: retraction is a command, and the operator limits are read.

def test_retract_through_the_command(store):
    flag_id = _pair(store, offer_title="Amp", offer_body="Bass amp.")["human"]["id"]
    gone = apply_upsert({"kind": "personal", "actor": PERSON, "retract": True, "id": flag_id}, store)
    assert gone["ok"] is True
    assert gone["result"]["status"] == "retracted"
    assert exposures(store) == []


def test_operator_limits_close_cap_and_expire(store, monkeypatch):
    values = dict(policy._DEFAULTS)
    monkeypatch.setattr(policy, "setting", lambda key: values[key])
    values["serendipilyst.listings_open"] = False
    with pytest.raises(FlagError) as closed:
        _pair(store, listed=True, place_id="lot")
    assert closed.value.code == "listings_closed"
    assert list_personal_flags(store, active_only=False) == []

    values["serendipilyst.listings_open"] = True
    values["serendipilyst.max_listings_per_steward"] = 2
    _pair(store, listed=True, place_id="lot", offer_title="Amp", offer_body="Bass amp.")
    with pytest.raises(FlagError) as capped:
        upsert_business_node(store, actor=PERSON, name="Foundry", listed=True, place_id="rail")
    assert capped.value.code == "limit_reached"
    # Saving a live listing again is a renewal, not a new one.
    assert upsert_personal_flag(store, actor=PERSON, holder="human", listed=True)["listed"] is True

    store.execute("UPDATE personal_flags SET listed_at = '2000-01-01', offered_at = '2000-01-01'")
    assert map_pins(store) == []
    assert exposures(store) == []


# 22: contact and payment details are caught in keys and in text.

@pytest.mark.parametrize("payload, caught", [
    ({"Email": "x"}, True),
    ({"phone_number": "x"}, True),
    ({"bio": "write me at amp@example.org"}, True),
    ({"bio": "call 707 555 0134 after six"}, True),
    ({"bio": "4" + "A" * 94}, True),
    ({"bio": "Doors at 8, 2026-10-13, $40 cover"}, False),
    ({"tip": "0.0000000000001"}, False),
    ({"human": {"declarations": ["mail amp@example.org"]}}, True),
])
def test_leaks_reads_keys_and_text(payload, caught):
    assert bool(leaks(payload)) is caught


# 8, 10: the routes run on the API server with a signed-in Steward.

def test_web_routes_need_a_steward_and_publish_no_addresses(store, monkeypatch):
    use_store(store)
    monkeypatch.setattr(web, "_key", b"k" * 32)
    code, _ = web.handle("POST", "/api/flags", {"command": "upsert", "args": {}}, None)
    assert code == 401
    code, made = web.handle("POST", "/api/flags", {"command": "upsert", "args": {
        "kind": "personal", "holder": "human", "displayName": "Al", "counterpartName": "Stew",
        "listed": True, "placeId": "lot", "offerTitle": "Amp", "offerBody": "Bass amp.",
    }}, "account-1")
    assert code == 200, made
    assert web.steward_address("account-1") == web.steward_address("account-1")
    assert web.steward_address("account-1") != web.steward_address("account-2")
    code, sheet = web.handle("GET", "/api/flags/sheet", None, None)
    assert code == 200
    assert sheet["pins"] and sheet["offers"]
    assert "a2a://agent/" not in json.dumps(sheet)
    code, mine = web.handle("GET", "/api/flags/mine", None, "account-1")
    assert [f["holder"] for f in mine["flags"]] and "owner" not in mine["flags"][0]
    code, refused = web.handle("POST", "/api/flags", {"command": "deal", "args": {
        "action": "interest", "flag_id": made["result"]["id"], "sentence": "Amp."}}, "account-1")
    assert code == 400 and "already yours" in refused["error"]["message"]


# 6, 10: the live model call, against a stand-in Ollama.

class _Ollama(BaseHTTPRequestHandler):
    seen: list[dict] = []
    tags = ["hermes3:8b"]

    def log_message(self, *args):
        pass

    def _send(self, payload):
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send({"models": [{"name": name} for name in self.tags]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Ollama.seen.append(body)
        self._send({"model": body["model"], "response": '{"item":"Sunday backline","amount":"1.5","unit":"xmr"}',
                    "done": True})


@pytest.fixture
def ollama(tmp_path, monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _Ollama)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = tmp_path / "agent.yaml"
    config.write_text(
        "inference:\n  local:\n"
        f"    endpoint: http://127.0.0.1:{server.server_address[1]}\n"
        "    model: hermes3:8b\n"
    )
    monkeypatch.setattr(reader, "_CONFIG", config)
    _Ollama.seen = []
    yield config
    server.shutdown()


def test_the_live_reader_asks_for_temperature_zero(ollama):
    reader.use_reader(None)
    terms = reader.read_terms(
        [{"sender": "@a", "content": "Sunday for 1.5?"}, {"sender": "@b", "content": "Yes."}],
        buyer="@a", seller="@b",
    )
    assert terms == {"item": "Sunday backline", "amount": "1.5", "unit": "XMR"}
    sent = _Ollama.seen[0]
    assert sent["options"] == {"temperature": 0, "seed": 7}
    assert sent["format"] == "json"
    assert "temperature" not in sent


def test_check_model_names_a_missing_tag(ollama):
    assert reader.check_model()["ok"] is True
    ollama.write_text(ollama.read_text().replace("hermes3:8b", "hermes-3-llama-3.1-8b"))
    missing = reader.check_model()
    assert missing["ok"] is False
    assert "not pulled" in missing["message"]


def test_a_busy_reader_says_so(ollama, monkeypatch):
    slots = threading.BoundedSemaphore(1)
    slots.acquire()
    monkeypatch.setattr(reader, "_slots", slots)
    monkeypatch.setattr(reader._slots, "acquire", lambda timeout=None: False)
    with pytest.raises(FlagError) as busy:
        reader._local_complete("hello")
    assert busy.value.code == "busy"


def test_configure_persists_flags(tmp_path):
    path = tmp_path / "data" / "serendipilyst.db"
    first = serendipilyst.configure(path)
    _pair(first)
    first.close()
    second = serendipilyst.configure(path)
    assert len(list_personal_flags(second)) == 2
    second.close()
    use_store(None)
    serendipilyst.use_chat(None)


def test_business_flag_offers_answer_at_the_node_inbox(store):
    node = upsert_business_node(store, actor=PERSON, name="Foundry")
    anchor_business_flag(store, actor=PERSON, node_id=node["id"], title="Backline", body="Sunday.")
    offer = exposures(store)[0]
    assert offer["inbox"] == node["inbox"]
    assert resolve_relay(store, offer["inbox"])["ref"] == f"node:{node['id']}"
