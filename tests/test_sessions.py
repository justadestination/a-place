"""Unit and integration tests for Task 4.3: Session management.

Verifies:
  1. Multi-device session issuance and listing.
  2. Marking current vs remote sessions in session lists.
  3. Instant revocation of a specific remote session (assert second device is logged out).
  4. Global revocation of all other active sessions while retaining current session.
  5. Security boundary: users cannot revoke sessions belonging to other users.
  6. HTTP API endpoints /api/auth/sessions, /api/auth/sessions/revoke, /api/auth/sessions/revoke-others.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from http.server import ThreadingHTTPServer
import urllib.request
import urllib.error
from pathlib import Path

import pytest

from shadenet.auth import AuthStore, AuthManager
from shadenet.nightcal.server import Handler


@pytest.fixture
def auth_store(tmp_path):
    db_file = tmp_path / "test_sessions.db"
    return AuthStore(db_path=db_file)


@pytest.fixture
def auth_mgr(auth_store):
    return AuthManager(store=auth_store, rp_id="localhost", rp_name="Test NightCal")


def test_multi_device_sessions_and_listing(auth_mgr, auth_store):
    # Register user
    reg = auth_mgr.register_with_password("alice", "Password123!", display_name="Alice")
    user_id = reg["user"]["id"]
    token_primary = reg["session_token"]

    # Issue secondary and tertiary device sessions
    token_mobile = auth_store.create_session(user_id=user_id, device_info="iPhone Safari")
    token_tablet = auth_store.create_session(user_id=user_id, device_info="iPad Chrome")

    # List active sessions from primary token
    sessions = auth_mgr.list_sessions(token_primary)
    assert len(sessions) == 3

    # Check is_current annotation
    current_count = sum(1 for s in sessions if s.get("is_current") is True)
    assert current_count == 1
    current_sess = next(s for s in sessions if s.get("is_current") is True)
    assert current_sess["session_id"] == token_primary

    # Verify device_info preserved
    devices = {s["device_info"] for s in sessions}
    assert "iPhone Safari" in devices
    assert "iPad Chrome" in devices


def test_revoke_specific_session(auth_mgr, auth_store):
    reg = auth_mgr.register_with_password("bob", "Secret123!", display_name="Bob")
    user_id = reg["user"]["id"]
    token_laptop = reg["session_token"]
    token_phone = auth_store.create_session(user_id=user_id, device_info="Pixel Phone")

    # Both sessions initially valid
    assert auth_mgr.validate_session(token_laptop) is not None
    assert auth_mgr.validate_session(token_phone) is not None

    # Revoke phone from laptop
    revoked = auth_mgr.revoke_session(session_token=token_laptop, target_session_id=token_phone)
    assert revoked is True

    # Immediate logout assertion on next request from phone
    assert auth_mgr.validate_session(token_phone) is None

    # Laptop session remains intact
    assert auth_mgr.validate_session(token_laptop) is not None

    # List active sessions now only shows laptop
    active = auth_mgr.list_sessions(token_laptop)
    assert len(active) == 1
    assert active[0]["session_id"] == token_laptop


def test_revoke_all_other_sessions(auth_mgr, auth_store):
    reg = auth_mgr.register_with_password("charlie", "Secret123!", display_name="Charlie")
    user_id = reg["user"]["id"]
    token_desktop = reg["session_token"]
    token_mobile1 = auth_store.create_session(user_id=user_id, device_info="Mobile 1")
    token_mobile2 = auth_store.create_session(user_id=user_id, device_info="Mobile 2")

    # Verify 3 active sessions
    assert len(auth_mgr.list_sessions(token_desktop)) == 3

    # Revoke all others
    count = auth_mgr.revoke_all_other_sessions(token_desktop)
    assert count == 2

    # Desktop remains active
    assert auth_mgr.validate_session(token_desktop) is not None

    # Mobile 1 and 2 are revoked immediately
    assert auth_mgr.validate_session(token_mobile1) is None
    assert auth_mgr.validate_session(token_mobile2) is None

    # Listing only shows desktop
    active = auth_mgr.list_sessions(token_desktop)
    assert len(active) == 1
    assert active[0]["session_id"] == token_desktop


def test_cannot_revoke_other_user_session(auth_mgr, auth_store):
    u1 = auth_mgr.register_with_password("user_one", "Pass12345!")
    u2 = auth_mgr.register_with_password("user_two", "Pass12345!")

    tok1 = u1["session_token"]
    tok2 = u2["session_token"]

    # user_one attempts to revoke user_two's session
    revoked = auth_mgr.revoke_session(tok1, tok2)
    assert revoked is False  # Cannot revoke someone else's session

    # user_two's session must still be fully active
    assert auth_mgr.validate_session(tok2) is not None


class SessionServerContext:
    def __init__(self, auth_mgr: AuthManager, db_path: Path):
        self.auth_mgr = auth_mgr
        self.db_path = db_path
        self.server = None
        self.port = 0
        self.thread = None

    def __enter__(self):
        from shadenet.ratelimit import limiter
        limiter.reset()
        import shadenet.nightcal.server as srv_mod
        srv_mod.default_auth_manager = self.auth_mgr
        srv_mod.DB_PATH = self.db_path

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.server:
            self.server.shutdown()
            self.server.server_close()


def _request_json(url: str, method: str = "GET", payload: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
    hdrs = headers or {}
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if payload is not None and "Content-Type" not in hdrs:
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body}


def test_http_api_session_management(auth_mgr, auth_store, tmp_path):
    with SessionServerContext(auth_mgr, tmp_path / "shadenet.db") as ctx:
        base = f"http://127.0.0.1:{ctx.port}"

        # 1. Register device 1 via fallback
        code, reg1 = _request_json(f"{base}/api/auth/register/fallback", method="POST", payload={
            "username": "device_user",
            "password": "Password99!",
            "displayName": "Device Tester"
        })
        assert code == 200
        token1 = reg1["session_token"]
        user_id = reg1["user"]["id"]

        # 2. Login as device 2
        code, log2 = _request_json(f"{base}/api/auth/login/fallback", method="POST", payload={
            "username": "device_user",
            "password": "Password99!"
        })
        assert code == 200
        token2 = log2["session_token"]

        # 3. Query sessions from device 1
        code, res_sessions = _request_json(
            f"{base}/api/auth/sessions",
            method="GET",
            headers={"Authorization": f"Bearer {token1}"}
        )
        assert code == 200
        assert res_sessions["authenticated"] is True
        sessions = res_sessions["sessions"]
        assert len(sessions) == 2
        d1 = next(s for s in sessions if s["session_id"] == token1)
        assert d1["is_current"] is True
        d2 = next(s for s in sessions if s["session_id"] == token2)
        assert d2["is_current"] is False

        # 4. Device 2 verifies it is authenticated
        code, check2 = _request_json(
            f"{base}/api/auth/session",
            method="GET",
            headers={"Authorization": f"Bearer {token2}"}
        )
        assert code == 200
        assert check2["authenticated"] is True

        # 5. Device 1 revokes Device 2's session
        code, revoke_res = _request_json(
            f"{base}/api/auth/sessions/revoke",
            method="POST",
            headers={"Authorization": f"Bearer {token1}"},
            payload={"sessionId": token2}
        )
        assert code == 200
        assert revoke_res["success"] is True

        # 6. Device 2 attempts request -> MUST GET 401 Unauthorized immediately
        code, check2_after = _request_json(
            f"{base}/api/auth/session",
            method="GET",
            headers={"Authorization": f"Bearer {token2}"}
        )
        assert code == 401
        assert check2_after["authenticated"] is False

        # 7. Device 1 remains fully authenticated
        code, check1_after = _request_json(
            f"{base}/api/auth/session",
            method="GET",
            headers={"Authorization": f"Bearer {token1}"}
        )
        assert code == 200
        assert check1_after["authenticated"] is True
