"""Unit tests for Account Deletion and Data Export (Task 4.5).

Verifies:
1. Full GDPR/CCPA export of user profile, passkeys, sessions, preferences, earmarks, votes.
2. Scrubbing of sensitive secrets (salt, password_hash) from export bundle.
3. Confirmation guard on account deletion (mismatched username rejected).
4. Full account deletion removing all associated records.
5. Zero residual rows for that user across all tables in SQLite store.
6. Immediate invalidation of all active sessions upon deletion.
"""

import json
import sqlite3
import pytest
from pathlib import Path
from shadenet.auth import AuthStore, AuthManager


@pytest.fixture
def temp_auth_manager(tmp_path: Path):
    db_file = tmp_path / "test_auth.db"
    store = AuthStore(db_path=db_file)
    # Ensure nightcal_tallies table exists for vote tests
    with store._get_connection() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS nightcal_tallies (
            event_id TEXT,
            steward_id TEXT,
            direction TEXT,
            verified INTEGER,
            updated_at REAL
        );
        """)
        con.commit()
    mgr = AuthManager(store=store)
    return mgr, store


def test_export_completeness(temp_auth_manager):
    mgr, store = temp_auth_manager
    reg = mgr.register_with_password("solaris", "secret_pass_123", display_name="Solaris Dawn")
    token = reg["session_token"]
    user_id = reg["user"]["id"]

    # Add preferences
    mgr.set_preferences(token, {"theme": "contrast", "notifications": True, "density": "compact"})

    # Add earmarks
    mgr.add_earmark(token, "evt_jazz_night_42")
    mgr.add_earmark(token, "evt_punk_matinee_99")

    # Seed tallies/votes in nightcal_tallies
    with store._get_connection() as con:
        con.execute(
            "INSERT INTO nightcal_tallies (event_id, steward_id, direction, verified, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("evt_jazz_night_42", reg["user"]["steward_id"], "up", 1, 1728470000.0)
        )
        con.commit()

    # Generate export
    export_bundle = mgr.export_account(token)

    assert export_bundle["format_version"] == "1.0"
    assert "GDPR/CCPA" in export_bundle["compliance"]
    assert export_bundle["user"]["username"] == "solaris"
    assert export_bundle["user"]["display_name"] == "Solaris Dawn"

    # Verify secrets are scrubbed
    assert "password_hash" not in export_bundle["user"]
    assert "salt" not in export_bundle["user"]

    # Verify preferences
    assert export_bundle["preferences"]["theme"] == "contrast"
    assert export_bundle["preferences"]["density"] == "compact"

    # Verify earmarks
    earmark_ids = [e["event_id"] for e in export_bundle["earmarks"]]
    assert "evt_jazz_night_42" in earmark_ids
    assert "evt_punk_matinee_99" in earmark_ids

    # Verify votes
    assert len(export_bundle["votes"]) == 1
    assert export_bundle["votes"][0]["event_id"] == "evt_jazz_night_42"
    assert export_bundle["votes"][0]["direction"] == "up"

    # Verify sessions
    assert len(export_bundle["sessions"]) >= 1


def test_deletion_confirmation_guard(temp_auth_manager):
    mgr, _ = temp_auth_manager
    reg = mgr.register_with_password("alex_mercer", "prototype_pass", display_name="Alex Mercer")
    token = reg["session_token"]

    # Attempt delete with wrong username confirmation
    with pytest.raises(ValueError, match="Confirmation username 'wrong_name' does not match"):
        mgr.delete_account(token, confirm_username="wrong_name")

    # Session still valid
    assert mgr.validate_session(token) is not None


def test_zero_residual_rows_after_deletion(temp_auth_manager):
    mgr, store = temp_auth_manager
    reg = mgr.register_with_password("delete_me_user", "temp_pass_456", display_name="Disposable")
    token = reg["session_token"]
    user_id = reg["user"]["id"]
    username = reg["user"]["username"]
    steward_id = reg["user"]["steward_id"]

    # Create multiple sessions, recovery codes, preferences, earmarks, and votes
    sess2 = store.create_session(user_id, device_info="Secondary Device")
    store.generate_recovery_codes(user_id)
    mgr.set_preferences(token, {"notifications": False})
    mgr.add_earmark(token, "evt_ambient_noon")
    store.create_recovery_escalation(username, "test@example.com", "Need help")

    with store._get_connection() as con:
        con.execute(
            "INSERT INTO nightcal_tallies (event_id, steward_id, direction, verified, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("evt_ambient_noon", steward_id, "up", 1, 1728470000.0)
        )
        con.commit()

    # Perform full deletion
    res = mgr.delete_account(token, confirm_username=username)
    assert res["success"] is True
    assert res["deleted_user_id"] == user_id

    # Verify sessions are invalidated
    assert mgr.validate_session(token) is None
    assert mgr.validate_session(sess2) is None

    # Assert ZERO residual rows in all tables
    with store._get_connection() as con:
        assert con.execute("SELECT COUNT(*) FROM users WHERE id = ? OR username = ?", (user_id, username)).fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM passkeys WHERE user_id = ?", (user_id,)).fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,)).fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM recovery_codes WHERE user_id = ?", (user_id,)).fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM auth_challenges WHERE user_id = ?", (user_id,)).fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM user_preferences WHERE user_id = ?", (user_id,)).fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM user_earmarks WHERE user_id = ?", (user_id,)).fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM recovery_escalations WHERE user_id = ? OR username = ?", (user_id, username)).fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM nightcal_tallies WHERE steward_id = ? OR steward_id = ?", (steward_id, user_id)).fetchone()[0] == 0


def test_export_unauthorized_fails(temp_auth_manager):
    mgr, _ = temp_auth_manager
    with pytest.raises(ValueError, match="Unauthorized"):
        mgr.export_account("invalid_or_expired_token")
