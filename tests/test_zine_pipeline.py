"""Tests for Autonomous Zine Newsroom Pipeline and Prediction Scorecards (Task 7.2)."""

import pytest
from shadenet.zine_automations import (
    run_newsroom_cycle,
    select_two_models,
    get_pending_editorial_queue,
    get_model_scorecards,
    MODEL_ROSTER,
)
from shadenet.nightcal.venue_products import (
    get_venue_merch,
    enrich_venue_with_products,
)


def test_model_selection():
    m1, m2 = select_two_models()
    assert m1["name"] != m2["name"]
    assert m1 in MODEL_ROSTER
    assert m2 in MODEL_ROSTER


def test_newsroom_cycle_calibration_flow():
    # Force two models to select same headline
    m1 = MODEL_ROSTER[0]
    m2 = MODEL_ROSTER[1]
    res = run_newsroom_cycle(override_models=(m1, m2), mock_mode=True)
    assert res["is_calibration"] is True
    assert len(res["articles"]) >= 1

    art = res["articles"][0]
    assert "Calibration Dispatch" in art["title"]
    assert art["status"] == "pending_editor_review"
    assert len(art["models_involved"]) == 2
    assert len(art["scorecard"]) >= 1

    # Verify scorecards have confidence and testable check-by dates
    for sc in art["scorecard"]:
        assert "confidence" in sc
        assert sc["confidence"] > 0
        assert "check_by" in sc
        assert "claim" in sc


def test_queue_and_scorecard_persistence():
    queue = get_pending_editorial_queue()
    assert isinstance(queue, list)
    assert len(queue) >= 1

    cards = get_model_scorecards()
    assert isinstance(cards, list)
    assert len(cards) >= 1
    assert any(c["confidence"] >= 70 for c in cards)


def test_venue_merch_enrichment():
    v = {"id": "ven_vintage_space", "name": "Vintage Space"}
    enriched = enrich_venue_with_products(v)
    assert enriched["has_shop"] is True
    assert len(enriched["merch_items"]) >= 2
    assert enriched["merch_items"][0]["type"] in ("token", "vinyl", "merch", "poster")
