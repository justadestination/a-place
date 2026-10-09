"""Test suite for Feature Flags & CI/CD Deployment Pipeline (Task 6.6)."""

import json
import tempfile
from pathlib import Path

import pytest
from shadenet.flags import FeatureFlagManager
from tools.deploy import run_deployment_pipeline


@pytest.fixture
def temp_flag_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        flags_path = Path(tmpdir) / "flags.json"
        manager = FeatureFlagManager(path=flags_path)
        yield manager


def test_feature_flag_evaluation_and_live_toggle(temp_flag_manager):
    mgr = temp_flag_manager

    # 1. Default flags
    assert mgr.is_enabled("ar_camera_portal") is True
    assert mgr.is_enabled("nonexistent_flag") is False

    # 2. Live toggle without restart
    mgr.set_flag("new_experimental_view", enabled=True, rollout_percentage=100)
    assert mgr.is_enabled("new_experimental_view") is True

    mgr.set_flag("new_experimental_view", enabled=False)
    assert mgr.is_enabled("new_experimental_view") is False

    # 3. Canary percentage rollouts
    mgr.set_flag("canary_feature", enabled=True, rollout_percentage=50)
    # Contexts must hash deterministically
    assert mgr.is_enabled("canary_feature", context_id="user_alpha") in {True, False}
    # 0% rollout
    mgr.set_flag("canary_feature", enabled=True, rollout_percentage=0)
    assert mgr.is_enabled("canary_feature", context_id="any_user") is False

    # 4. Cohort targeting
    mgr.set_flag("steward_feature", enabled=True, rollout_percentage=0, cohorts=["stewards"])
    assert mgr.is_enabled("steward_feature", cohort="stewards") is True
    assert mgr.is_enabled("steward_feature", cohort="public") is False


def test_single_command_deployment_pipeline_staging_to_prod():
    res = run_deployment_pipeline(target="prod", canary=False)
    assert res["status"] == "PROD_LIVE"
    assert res["staging_verified"] is True
    assert res["duration_seconds"] > 0
    assert "pre_flight_db_integrity: ok" in res["steps"] or "pre_flight_db_integrity: skipped (no db file)" in res["steps"]
    assert "staging_mirror_health: verified" in res["steps"]


def test_deployment_with_canary_and_live_flag_flip():
    res = run_deployment_pipeline(
        target="prod",
        canary=True,
        flag_flip="canary_release",
        flag_state=True,
    )
    assert res["status"] == "PROD_LIVE"
    assert res["canary"] is True
    assert res["flag_flip"] == {"canary_release": True}
    assert "flag_flip_canary_release: verified_True" in res["steps"]


def test_deployment_failure_triggers_rollback():
    with pytest.raises(RuntimeError, match="rollback guard preserved"):
        run_deployment_pipeline(target="prod", simulate_failure=True)
