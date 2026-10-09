"""Entity pages and bidirectional links (Task 2.13)."""

import pytest

from shadenet.nightcal.entity_links import (
    article_matches_entity,
    articles_for_entity,
    entities_for_event,
    events_for_entity,
)
from shadenet.nightcal.schemas import SchemaValidationError, validate_entity


PROMOTER = {"id": "ent_promoter_lumen", "name": "Lumen Presents", "status": "active", "type": "promoter"}
BAND = {"id": "ent_band_wave", "name": "Subterranean Wave Syndicate", "status": "active", "type": "band"}
COMEDIAN = {"id": "ent_comic_null", "name": "Mara Voss", "status": "active", "type": "comedian"}
ENTITIES = [PROMOTER, BAND, COMEDIAN]
EVENT = {
    "id": "evt_wave_night",
    "title": "Subterranean Wave Syndicate",
    "entityIds": ["ent_band_wave"],
    "performers": [
        {"name": "Subterranean Wave Syndicate", "id": "ent_band_wave", "type": "band"},
        {"name": "Mara Voss", "id": "ent_comic_null", "type": "comedian"},
    ],
}
ARTICLE = {"id": "zine_wave_note", "title": "A night with Subterranean Wave Syndicate", "type": "article"}


@pytest.mark.parametrize("kind,payload", [
    ("promoter", {"id": "ent_promoter_lumen", "name": "Lumen Presents"}),
    ("band", {"id": "ent_band_wave", "name": "Subterranean Wave Syndicate"}),
    ("comedian", {"id": "ent_comic_null", "name": "Mara Voss"}),
])
def test_schema_accepts_each_entity_type(kind, payload):
    saved = validate_entity(kind, payload)
    assert saved["type"] == kind
    assert saved["name"] == payload["name"]
    assert saved["status"] == "active"


def test_unknown_entity_type_rejected():
    with pytest.raises(SchemaValidationError):
        validate_entity("other", {"id": "ent_other_paper", "name": "Night Paper"})


def test_event_and_entity_links_resolve_both_ways():
    assert [item["id"] for item in entities_for_event(EVENT, ENTITIES)] == ["ent_band_wave", "ent_comic_null"]
    assert [item["id"] for item in events_for_entity(BAND, [EVENT])] == ["evt_wave_night"]
    assert events_for_entity(PROMOTER, [EVENT]) == []


def test_article_that_names_an_entity_links_only_that_entity():
    assert article_matches_entity(ARTICLE, BAND) is True
    assert [item["id"] for item in articles_for_entity(BAND, [ARTICLE])] == ["zine_wave_note"]
    assert article_matches_entity(ARTICLE, COMEDIAN) is False
    assert article_matches_entity({"title": "Not a real act"}, BAND) is False
