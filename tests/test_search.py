"""Full-text search unit and ranking tests (Task 5.6)."""

import pytest
import tempfile
from pathlib import Path
from shadenet.towncrier.store import Store
from shadenet.search import build_search_index, search, sanitize_query


@pytest.fixture
def test_store(tmp_path):
    store = Store(tmp_path / "test_search.db")
    store.upsert_source("test", "test", "https://example.com")
    v1 = store.ensure_venue("The Velvet Lounge", address="100 4th Street", city="Santa Rosa", state="CA")
    v2 = store.ensure_venue("Riverfront Taproom", address="200 5th Street", city="Santa Rosa", state="CA")

    # Events: one with title match, one with body match
    store.upsert_listing(
        source_id="test",
        external_id="evt_1",
        url="https://example.com/1",
        title_raw="Acoustic Jazz Showcase",
        title_norm="acoustic jazz showcase",
        description="A quiet evening of traditional folk music.",
        starts_at="2026-10-15T20:00:00+00:00",
        venue_id=v1,
        venue_name_raw="The Velvet Lounge",
    )
    store.upsert_listing(
        source_id="test",
        external_id="evt_2",
        url="https://example.com/2",
        title_raw="Friday Night Dance Party",
        title_norm="friday night dance party",
        description="Features live jazz improvisations late into the night.",
        starts_at="2026-10-16T22:00:00+00:00",
        venue_id=v2,
        venue_name_raw="Riverfront Taproom",
    )

    from shadenet.towncrier.resolve import Resolver
    Resolver(store).resolve()

    articles = [
        {
            "id": "art_1",
            "slug": "sonoma-jazz-history",
            "title": "History of Sonoma County Jazz",
            "author": "Archivist",
            "body": "Tracing the vibrant roots of jazz across North Bay venues.",
        }
    ]
    build_search_index(store, articles)
    return store


def test_sanitize_query():
    assert sanitize_query("") == ""
    assert sanitize_query("   ") == ""
    assert sanitize_query('""') == ""
    assert sanitize_query('***:::^^^') == ""
    # Exact phrase preserved
    assert sanitize_query('"acoustic jazz"') == '"acoustic jazz"'
    # Normal tokens tokenized with trailing prefix match
    assert sanitize_query('acoustic jazz') == '"acoustic" AND "jazz"*'


def test_empty_and_gibberish_queries(test_store):
    res_empty = search(test_store, "")
    assert res_empty["total"] == 0
    assert res_empty["duration_ms"] < 500

    res_gibberish = search(test_store, "!!!@@@###$$$%%%^^^&&&***")
    assert res_gibberish["total"] == 0
    assert res_gibberish["duration_ms"] < 500


def test_title_outranks_body(test_store):
    # 'Acoustic Jazz Showcase' has 'jazz' in title
    # 'Friday Night Dance Party' has 'jazz' only in body
    res = search(test_store, "jazz")
    assert res["total"] >= 2
    spots = res["results"]["spots"]
    assert len(spots) >= 2
    # The title match must rank first (lower rank score)
    assert spots[0]["title"] == "Acoustic Jazz Showcase"
    assert spots[1]["title"] == "Friday Night Dance Party"


def test_grouped_results(test_store):
    res = search(test_store, "jazz")
    # Must have both spots and expressions (zine)
    assert len(res["results"]["spots"]) >= 1
    assert len(res["results"]["expressions"]) >= 1
    assert res["results"]["expressions"][0]["title"] == "History of Sonoma County Jazz"


def test_spaces_search(test_store):
    res = search(test_store, "Velvet")
    assert len(res["results"]["spaces"]) == 1
    assert res["results"]["spaces"][0]["title"] == "The Velvet Lounge"


def test_sub_500ms_performance(test_store):
    res = search(test_store, "showcase")
    assert res["duration_ms"] < 500
