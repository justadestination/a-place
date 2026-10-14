"""The House door as the NightCal server serves it (operator mail, R8)."""

from __future__ import annotations

import json
from pathlib import Path

from shadenet.house import House, RULES_PATH

from steward.stamp import mint  # importable once shadenet.house has put vendor/ on the path

AT = "2026-10-13T20:00:00Z"


def stamped(text: str, mail_id: str = "m-1", at: str = AT) -> dict:
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    mail = {"mail_id": mail_id, "case_id": None, "text": text}
    return {"mail": mail, "stamp": mint(mail, at, rules["parameters"]["operator_stamp_bits"])}


def test_stamped_mail_is_filed(tmp_path: Path) -> None:
    house = House(ledger=tmp_path / "inbox.jsonl")
    code, body = house.operator_mail(stamped("the door works"), arrived_at=AT)
    assert code == 202 and body == {"filed": "m-1"}
    records = [json.loads(line) for line in (tmp_path / "inbox.jsonl").read_text().splitlines()]
    assert records[-1]["to"] == "filed"


def test_unstamped_mail_is_refused_and_not_filed(tmp_path: Path) -> None:
    house = House(ledger=tmp_path / "inbox.jsonl")
    request = stamped("no work done")
    request["stamp"]["nonce"] = "0"
    code, body = house.operator_mail(request, arrived_at=AT)
    assert code == 400 and "refused" in body
    assert not (tmp_path / "inbox.jsonl").exists()


def test_replayed_mail_is_refused(tmp_path: Path) -> None:
    house = House(ledger=tmp_path / "inbox.jsonl")
    request = stamped("once only")
    assert house.operator_mail(request, arrived_at=AT)[0] == 202
    assert house.operator_mail(request, arrived_at="2026-10-13T20:01:00Z")[0] == 400


def test_sender_cannot_claim_a_steward(tmp_path: Path) -> None:
    house = House(ledger=tmp_path / "inbox.jsonl")
    request = stamped("pretending", mail_id="m-2")
    request["steward_id"] = "stw-somebody-else"
    code, _ = house.operator_mail(request, arrived_at=AT)
    assert code == 202
    filed = [json.loads(line) for line in (tmp_path / "inbox.jsonl").read_text().splitlines()][-1]
    assert filed["event"]["payload"]["steward_id"] is None


def test_non_object_body_is_refused(tmp_path: Path) -> None:
    house = House(ledger=tmp_path / "inbox.jsonl")
    assert house.operator_mail(["not", "an", "object"], arrived_at=AT)[0] == 400
    assert house.operator_mail({}, arrived_at=AT)[0] == 400
