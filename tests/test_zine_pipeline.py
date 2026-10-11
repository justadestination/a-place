"""Tests for Autonomous Zine Newsroom Pipeline and Prediction Scorecards (Task 7.2)."""

import pytest
from shadenet.zine_automations import (
    run_newsroom_cycle,
    select_two_models,
    get_pending_editorial_queue,
    get_model_scorecards,
    validate_word_count_and_read_time,
    verify_article_sources,
    verify_editorial_charter,
    check_fallacy_and_libel_guardrails,
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
    assert "compliance" in art
    assert art["compliance"]["cleared_for_publication"] is True
    assert "reading_time" in art

    # Verify scorecards have confidence and testable check-by dates
    for sc in art["scorecard"]:
        assert "confidence" in sc
        assert sc["confidence"] > 0
        assert "check_by" in sc
        assert "claim" in sc


def test_editorial_charter_verification():
    valid_art = {
        "title": "Acoustic Attenuation in Downtown Corridors",
        "executive_summary": "Analysis of sound reflection along 4th Street.",
        "dossier": {"overview": "Decibel drops follow inverse-square decay modified by street tree foliage."},
        "headline_ref": {"id": "ref-1", "url": "https://srcity.org/2180/Noise-Regulations"},
        "sources": ["https://srcity.org/2180/Noise-Regulations"],
        "scorecard": [{"claim": "Tree canopy absorbs 3dB", "check_by": "2027-01-01"}],
    }
    report = verify_editorial_charter(valid_art)
    assert report["cleared_for_publication"] is True
    assert report["ground_truth_verified"] is True
    assert report["sources"]["valid"] is True
    assert report["length_and_read_time"]["is_within_limit"] is True


def test_word_count_and_read_time_limits():
    # Under limit
    ok_res = validate_word_count_and_read_time(800)
    assert ok_res["is_within_limit"] is True
    assert ok_res["requires_chaining"] is False
    assert "min read" in ok_res["read_time_label"]

    # Over 1400 words requires backlink chaining
    over_res = validate_word_count_and_read_time(1500)
    assert over_res["is_within_limit"] is False
    assert over_res["requires_chaining"] is True


def test_article_sources_verification():
    assert verify_article_sources([])["valid"] is False
    assert verify_article_sources(["not-a-url"])["valid"] is False
    assert verify_article_sources(["https://srcity.org/noise"])["valid"] is True


def test_fallacy_and_libel_guardrails():
    # Clean text passes
    clean_check = check_fallacy_and_libel_guardrails("The council vote was approved 4-1 according to public minutes.")
    assert clean_check["passed"] is True
    assert len(clean_check["flags"]) == 0

    # Defamatory / ad-hominem terms fail
    flagged_check = check_fallacy_and_libel_guardrails("The mayor is an absolute idiot and a corrupt crook.")
    assert flagged_check["passed"] is False
    assert "corrupt crook" in flagged_check["flags"]
    assert "idiot" in flagged_check["flags"]

    # Defamatory article blocked from publication
    bad_art = {
        "title": "Corrupt crook spotted downtown",
        "executive_summary": "Unsubstantiated attacks on local figures.",
        "headline_ref": {"id": "ref-1", "url": "https://srcity.org/2180/Noise-Regulations"},
        "sources": ["https://srcity.org/2180/Noise-Regulations"],
    }
    report = verify_editorial_charter(bad_art)
    assert report["cleared_for_publication"] is False
    assert report["zero_libel_or_slander"] is False


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
