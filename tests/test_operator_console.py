"""Unit and integration tests for Task 6.3: Operator Console.

Verifies:
  1. Health, moderation queue, tally stats, key management, scraper and sync status.
  2. Operator can moderate content (approve, remove, dismiss) without touching a terminal.
  3. Operator can rotate cryptographic keys and track rotation history.
  4. HTTP endpoints /operator, /api/operator/status, /api/operator/moderation, /api/operator/keys/rotate.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import ThreadingHTTPServer
import urllib.request
import urllib.error

import pytest

from shadenet.operator import (
    get_operator_status,
    moderate_queue_item,
    rotate_active_key,
)
from shadenet.nightcal.server import Handler


def test_operator_status_structure():
    status = get_operator_status()
    assert "health" in status
    assert status["health"]["status"] == "healthy"
    assert "uptime_seconds" in status["health"]
    assert "version" in status["health"]

    assert "moderation_queue" in status
    assert isinstance(status["moderation_queue"], list)

    assert "tally_stats" in status
    assert "total_votes" in status["tally_stats"]
    assert "positive_votes" in status["tally_stats"]

    assert "key_management" in status
    assert "active_key" in status["key_management"]
    assert status["key_management"]["active_key"]["algorithm"] == "Ed25519"

    assert "scraper_status" in status
    assert "sync_mesh_status" in status
    assert status["sync_mesh_status"]["peer_count"] >= 1


def test_moderation_queue_actions():
    status = get_operator_status()
    queue = status["moderation_queue"]
    if not queue:
        pytest.skip("Queue empty")

    item_id = queue[0]["id"]
    
    # Approve action
    res = moderate_queue_item(item_id, "approve", operator_note="Approved by test")
    assert res["success"] is True
    assert res["action"] == "approve"
    assert res["item"]["status"] == "approve"

    # Verify item is removed from pending queue
    new_status = get_operator_status()
    remaining_ids = [it["id"] for it in new_status["moderation_queue"]]
    assert item_id not in remaining_ids

    # Invalid action raises ValueError
    with pytest.raises(ValueError):
        moderate_queue_item("nonexistent", "destroy_everything")

    # Non-existent item raises KeyError
    with pytest.raises(KeyError):
        moderate_queue_item("missing-id-9999", "remove")


def test_key_rotation_lifecycle():
    initial_status = get_operator_status()
    old_key_id = initial_status["key_management"]["active_key"]["key_id"]
    old_rot_count = initial_status["key_management"]["active_key"].get("rotation_count", 0)

    res = rotate_active_key(operator_identity="automated-test")
    assert res["success"] is True
    assert res["old_key_id"] == old_key_id
    assert res["new_key"]["key_id"] != old_key_id
    assert res["new_key"]["rotation_count"] == old_rot_count + 1

    # Verify new status reflects rotated key
    post_status = get_operator_status()
    assert post_status["key_management"]["active_key"]["key_id"] == res["new_key"]["key_id"]


def test_operator_http_status_requires_sign_in(live_server):
    req = urllib.request.Request(f"{live_server}/api/operator/status")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 401


def test_operator_http_key_rotation_requires_sign_in(live_server):
    req = urllib.request.Request(
        f"{live_server}/api/operator/keys/rotate",
        data=json.dumps({"operator": "attacker"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 401


def test_operator_http_status_api(ops_client):
    status, data, _ = ops_client.request("GET", "/api/operator/status")
    assert status == 200
    assert data["health"]["status"] == "healthy"
    assert "tally_stats" in data


def test_operator_http_key_rotation(ops_client):
    status, data, _ = ops_client.request("POST", "/api/operator/keys/rotate", {"operator": "http-test-runner"})
    assert status == 200
    assert data["success"] is True
    assert "new_key" in data


def test_operator_page_redirects_to_ops_console(live_server):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    with pytest.raises(urllib.error.HTTPError) as exc:
        opener.open(f"{live_server}/operator")
    assert exc.value.code == 302
    assert exc.value.headers["Location"] == "/ops/"
