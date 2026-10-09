"""Test suite for Secrets Management & Zero-Downtime Rotation (Task 6.5)."""

import os
import stat
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from shadenet.secret_store import SecretStore


@pytest.fixture
def temp_secrets_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "secrets.json"
        store = SecretStore(path=store_path, default_overlap=300)
        yield store


def test_secret_store_initialization_and_permissions(temp_secrets_store):
    store = temp_secrets_store
    assert store.path.exists()

    # Verify POSIX 0600 permissions
    mode = store.path.stat().st_mode & 0o777
    assert mode == 0o600

    active = store.get_active_fleet_key()
    assert active["status"] == "active"
    assert active["algorithm"] == "Ed25519"
    assert len(active["secret"]) >= 32

    op_token = store.get_operator_token()
    assert len(op_token) == 64


def test_zero_downtime_rotation_dual_key_validation(temp_secrets_store):
    store = temp_secrets_store

    initial_active = store.get_active_fleet_key()
    old_secret = initial_active["secret"]
    old_key_id = initial_active["key_id"]

    # Initial verification
    assert store.verify_fleet_key(old_secret) is True
    assert store.verify_fleet_key("bad-secret") is False

    # Execute rotation with 300s grace window
    res = store.rotate_fleet_key(overlap_seconds=300, rotated_by="staging-drill")
    assert res["status"] == "ROTATED"
    assert res["old_key_id"] == old_key_id

    new_active = store.get_active_fleet_key()
    new_secret = new_active["secret"]
    assert new_active["key_id"] != old_key_id

    # ZERO DOWNTIME DUAL-KEY VERIFICATION:
    # 1. Old in-flight requests with old key must SUCCEED
    assert store.verify_fleet_key(old_secret) is True

    # 2. New requests with new key must SUCCEED
    assert store.verify_fleet_key(new_secret) is True

    # 3. Invalid credentials must still FAIL
    assert store.verify_fleet_key("unauthorized-key") is False


def test_expired_grace_key_rejection(temp_secrets_store):
    store = temp_secrets_store

    initial_active = store.get_active_fleet_key()
    old_secret = initial_active["secret"]

    # Rotate with 0 second overlap (immediate expiration)
    store.rotate_fleet_key(overlap_seconds=-1, rotated_by="fast-retire")

    # Prune expired keys
    pruned = store.prune_expired_grace_keys()
    assert len(pruned) >= 1

    # Old key must now be rejected
    assert store.verify_fleet_key(old_secret) is False

    # New key must remain valid
    new_secret = store.get_active_fleet_key()["secret"]
    assert store.verify_fleet_key(new_secret) is True


def test_simulated_high_throughput_traffic_across_rotation(temp_secrets_store):
    """Assert zero errors across high throughput traffic during key rollover."""
    store = temp_secrets_store

    old_secret = store.get_active_fleet_key()["secret"]
    total_requests = 200
    errors = 0

    # Simulate in-flight traffic before, during, and after rotation
    for i in range(total_requests):
        if i == 50:
            # Trigger rotation mid-stream
            store.rotate_fleet_key(overlap_seconds=60)
            new_secret = store.get_active_fleet_key()["secret"]

        # Mix of old in-flight tokens and newly issued tokens
        token_to_verify = old_secret if i < 150 else new_secret
        if not store.verify_fleet_key(token_to_verify):
            errors += 1

    assert errors == 0, f"Encountered {errors} failed authentications during rotation!"
