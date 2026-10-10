"""Tests for Operator Steward & Matrix Command Interface (Task 7.2)."""

import pytest
from shadenet.operator_steward import OperatorSteward


@pytest.fixture
def steward():
    return OperatorSteward(steward_id="test-ops-steward")


def test_command_help(steward):
    res = steward.process_command("!help")
    assert res["status"] == "success"
    assert "!status" in res["message"]
    assert "!rotate-keys" in res["message"]


def test_command_status(steward):
    res = steward.process_command("!status")
    assert res["status"] == "success"
    assert "Node Status:" in res["message"]
    assert "Active Key:" in res["message"]
    assert "data" in res


def test_command_scrape_drill(steward):
    res = steward.process_command("!scrape")
    assert res["status"] in ("success", "warning")
    assert "Scraper supervision" in res["message"]


def test_command_rotate_keys(steward):
    res = steward.process_command("!rotate-keys")
    assert res["status"] == "success"
    assert "Key rotation drill complete" in res["message"]


def test_command_moderation(steward):
    res = steward.process_command("!moderation")
    assert res["status"] == "success"
    assert "Pending Moderation Items:" in res["message"]


def test_unknown_command(steward):
    res = steward.process_command("!unknown_action")
    assert res["status"] == "error"
    assert "Unknown command" in res["message"]


def test_alert_formatting(steward):
    alert = steward.format_alert_payload("Scraper blocked by Cloudflare", "Encountered Turnstile challenge", severity="critical")
    assert alert["msgtype"] == "m.text"
    assert "🚨" in alert["body"]
    assert alert["severity"] == "critical"
