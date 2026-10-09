"""Venue owner edits and news blurbs (Task 2.14)."""

import pytest

from shadenet.nightcal.venue_edits import add_blurb, add_event, claim, get_overlay, update_info


@pytest.fixture
def edits_file(tmp_path, monkeypatch):
    monkeypatch.setenv("VENUE_EDITS_PATH", str(tmp_path / "edits.json"))
    monkeypatch.delenv("NIGHTCAL_OPERATORS", raising=False)
    return tmp_path


def test_owner_can_update_add_a_show_and_publish_news(edits_file):
    owner = {"id": "user_ada", "username": "ada"}
    claim("ven_quick_edit", owner)
    updated = update_info("ven_quick_edit", owner, {"name": "The Cellar", "address": "1 Main Street"})
    assert updated["name"] == "The Cellar"
    assert updated["address"] == "1 Main Street"
    added = add_event("ven_quick_edit", owner, {"title": "Friday set", "date": "2026-10-16", "start": "20:00"})
    assert added["events"][0]["title"] == "Friday set"
    published = add_blurb("ven_quick_edit", owner, "Doors at eight", "The Friday set starts at eight.")
    assert published["blurbs"][0]["title"] == "Doors at eight"
    overlay = get_overlay("ven_quick_edit")
    assert overlay["blurbs"][0]["content"] == "The Friday set starts at eight."


def test_another_user_cannot_edit(edits_file):
    claim("ven_quick_edit", {"id": "user_ada", "username": "ada"})
    with pytest.raises(PermissionError):
        update_info("ven_quick_edit", {"id": "user_bob", "username": "bob"}, {"address": "somewhere else"})


def test_operator_can_edit_any_venue(edits_file, monkeypatch):
    claim("ven_quick_edit", {"id": "user_ada", "username": "ada"})
    monkeypatch.setenv("NIGHTCAL_OPERATORS", "op")
    updated = update_info("ven_quick_edit", {"id": "user_op", "username": "op"}, {"address": "2 Main Street"})
    assert updated["address"] == "2 Main Street"
