"""Unit tests for Preference & Settings Tabs (Task 4.6).

Verifies:
1. Setting and retrieving user preferences (theme, density, text scale, notifications, muted venues).
2. Deep merge / update of preference keys without losing unmentioned settings.
3. Cross-session persistence across multiple devices for the same user.
4. Unauthorized access rejection when session is invalid or revoked.
"""

import pytest
from pathlib import Path
from shadenet.auth import AuthStore, AuthManager


@pytest.fixture
def auth_env(tmp_path: Path):
    db_file = tmp_path / "test_prefs.db"
    store = AuthStore(db_path=db_file)
    mgr = AuthManager(store=store)
    return mgr, store


def test_preferences_crud_and_persistence(auth_env):
    mgr, store = auth_env
    reg = mgr.register_with_password("luna_steward", "secure_steward_key", display_name="Luna")
    token1 = reg["session_token"]
    user_id = reg["user"]["id"]

    # Initial preferences should be empty
    prefs0 = mgr.get_preferences(token1)
    assert prefs0 == {}

    # Set full preferences
    initial_prefs = {
        "theme": "dark",
        "density": "compact",
        "text_scale": 1.25,
        "motion": "reduce",
        "notifications": {
            "earmark_reminders": True,
            "cancellation_alerts": True,
            "daily_digest": False,
        },
        "muted_venues": ["ven_noisy_cellar", "ven_rowdy_pub"],
        "default_scope": "nights",
        "steward_handle": "steward_luna",
    }
    saved = mgr.set_preferences(token1, initial_prefs)
    assert saved["user_id"] == user_id
    assert saved["preferences"]["theme"] == "dark"
    assert saved["preferences"]["density"] == "compact"
    assert "ven_noisy_cellar" in saved["preferences"]["muted_venues"]

    # Retrieve preferences
    retrieved = mgr.get_preferences(token1)
    assert retrieved["theme"] == "dark"
    assert retrieved["density"] == "compact"
    assert retrieved["text_scale"] == 1.25
    assert retrieved["motion"] == "reduce"
    assert retrieved["notifications"]["earmark_reminders"] is True
    assert retrieved["muted_venues"] == ["ven_noisy_cellar", "ven_rowdy_pub"]
    assert retrieved["steward_handle"] == "steward_luna"


def test_preferences_cross_session_sync(auth_env):
    mgr, store = auth_env
    reg = mgr.register_with_password("orion_night", "orion_pass_123", display_name="Orion")
    token_desktop = reg["session_token"]
    user_id = reg["user"]["id"]

    # Create secondary session (e.g. mobile phone)
    token_mobile = store.create_session(user_id, device_info="Mobile Safari")

    # Update preferences from desktop
    mgr.set_preferences(token_desktop, {
        "theme": "light",
        "density": "spacious",
        "muted_venues": ["ven_industrial_hall"],
    })

    # Read preferences from mobile session
    mobile_prefs = mgr.get_preferences(token_mobile)
    assert mobile_prefs["theme"] == "light"
    assert mobile_prefs["density"] == "spacious"
    assert mobile_prefs["muted_venues"] == ["ven_industrial_hall"]


def test_preferences_partial_update_keeps_other_sections(auth_env):
    mgr, _store = auth_env
    reg = mgr.register_with_password("partial_steward", "partial_pass_123", display_name="Partial")
    token = reg["session_token"]
    mgr.set_preferences(token, {
        "theme": "dark",
        "notifications": {"earmark_reminders": True, "daily_digest": False},
        "muted_venues": ["ven_keep"],
    })
    mgr.set_preferences(token, {
        "notifications": {"daily_digest": True},
        "density": "compact",
    })
    stored = mgr.get_preferences(token)
    assert stored["theme"] == "dark"
    assert stored["density"] == "compact"
    assert stored["muted_venues"] == ["ven_keep"]
    assert stored["notifications"]["earmark_reminders"] is True
    assert stored["notifications"]["daily_digest"] is True


def test_preferences_unauthorized_rejection(auth_env):
    mgr, _ = auth_env
    with pytest.raises(ValueError, match="Unauthorized"):
        mgr.get_preferences("invalid_token")

    with pytest.raises(ValueError, match="Unauthorized"):
        mgr.set_preferences("invalid_token", {"theme": "dark"})
