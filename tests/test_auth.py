"""Unit and integration tests for Task 4.1: Username / passkey entry.

Verifies:
  1. Passkey (WebAuthn / FIDO2) registration and authentication flow.
  2. Username fallback registration and password verification.
  3. Session lifecycle: issuance, verification, and revocation (logout).
  4. HTTP endpoints /api/auth/* on NightCal server.
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

from shadenet.auth import AuthStore, AuthManager, _hash_secret, _verify_secret
from shadenet.nightcal.server import Handler


@pytest.fixture
def test_auth_store(tmp_path):
    db_file = tmp_path / "test_auth.db"
    return AuthStore(db_path=db_file)


@pytest.fixture
def auth_mgr(test_auth_store):
    return AuthManager(store=test_auth_store, rp_id="localhost", rp_name="Test NightCal")


# --- 1. Store & Crypto Primitives Tests ---

def test_password_hashing():
    salt, hash_val = _hash_secret("correct-horse-battery")
    assert _verify_secret("correct-horse-battery", salt, hash_val) is True
    assert _verify_secret("wrong-password", salt, hash_val) is False


def test_user_creation_and_uniqueness(test_auth_store):
    u = test_auth_store.create_user("alice", display_name="Alice Wonder")
    assert u["username"] == "alice"
    assert u["display_name"] == "Alice Wonder"
    assert "usr_" in u["id"]

    with pytest.raises(ValueError, match="already registered"):
        test_auth_store.create_user("alice")


def test_challenge_single_use_and_expiry(test_auth_store):
    ch = test_auth_store.create_challenge(purpose="registration", ttl_seconds=10)
    # First consumption succeeds
    assert test_auth_store.verify_and_consume_challenge(ch, purpose="registration") is True
    # Second consumption fails (single-use)
    assert test_auth_store.verify_and_consume_challenge(ch, purpose="registration") is False


# --- 2. Passkey WebAuthn Ceremony Tests ---

def test_passkey_registration_flow(auth_mgr):
    # 1. Options
    opts = auth_mgr.generate_registration_options("bob", display_name="Bob Builder")
    assert opts["rp"]["name"] == "Test NightCal"
    assert opts["user"]["name"] == "bob"
    assert "challenge" in opts

    # 2. Verify
    cred_id = "cred_raw_bytes_simulated_id_12345"
    pub_key = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA..."
    res = auth_mgr.verify_registration(
        username="bob",
        credential_id=cred_id,
        public_key=pub_key,
        client_challenge=opts["challenge"],
        display_name="Bob Builder",
        device_nickname="MacBook TouchID",
    )
    assert res["success"] is True
    assert res["user"]["username"] == "bob"
    assert "sess_" in res["session_token"]
    assert res["credential"]["nickname"] == "MacBook TouchID"

    # Verify session is immediately active
    sess = auth_mgr.validate_session(res["session_token"])
    assert sess is not None
    assert sess["username"] == "bob"


def test_passkey_login_flow(auth_mgr):
    # Setup registered user
    reg_opts = auth_mgr.generate_registration_options("carol")
    cred_id = "cred_carol_passkey_777"
    auth_mgr.verify_registration(
        username="carol",
        credential_id=cred_id,
        public_key="public_key_bytes_xyz",
        client_challenge=reg_opts["challenge"],
    )

    # 1. Login options
    login_opts = auth_mgr.generate_login_options("carol")
    assert login_opts["challenge"]
    assert len(login_opts["allowCredentials"]) == 1
    assert login_opts["allowCredentials"][0]["id"] == cred_id

    # 2. Login verification
    login_res = auth_mgr.verify_login(
        credential_id=cred_id,
        client_challenge=login_opts["challenge"],
        device_info="iPhone FaceID",
    )
    assert login_res["success"] is True
    assert login_res["user"]["username"] == "carol"
    assert "sess_" in login_res["session_token"]

    # Verify session is valid
    sess = auth_mgr.validate_session(login_res["session_token"])
    assert sess is not None
    assert sess["username"] == "carol"


def test_passkey_login_bad_challenge_rejected(auth_mgr):
    reg_opts = auth_mgr.generate_registration_options("dave")
    cred_id = "cred_dave_passkey_888"
    auth_mgr.verify_registration(
        username="dave",
        credential_id=cred_id,
        public_key="pubkey",
        client_challenge=reg_opts["challenge"],
    )

    with pytest.raises(ValueError, match="Invalid or expired"):
        auth_mgr.verify_login(credential_id=cred_id, client_challenge="forged_challenge_value")


# --- 3. Username Fallback Tests ---

def test_username_password_registration_and_login(auth_mgr):
    reg = auth_mgr.register_with_password("eve", "Secret123Pass!", display_name="Eve Online")
    assert reg["success"] is True
    assert reg["user"]["username"] == "eve"
    assert "sess_" in reg["session_token"]

    # Login with valid password
    login_res = auth_mgr.login_with_password("eve", "Secret123Pass!")
    assert login_res["success"] is True
    assert login_res["user"]["username"] == "eve"

    # Login with invalid password
    with pytest.raises(ValueError, match="Invalid username or credentials"):
        auth_mgr.login_with_password("eve", "WrongPass123!")


def test_user_without_password_fallback_rejected(auth_mgr):
    reg_opts = auth_mgr.generate_registration_options("frank")
    auth_mgr.verify_registration(
        username="frank",
        credential_id="cred_frank_only",
        public_key="key",
        client_challenge=reg_opts["challenge"],
    )

    with pytest.raises(ValueError, match="No fallback secret configured"):
        auth_mgr.login_with_password("frank", "some_guess")


# --- 4. Session Revocation / Logout Tests ---

def test_session_logout_lifecycle(auth_mgr):
    reg = auth_mgr.register_with_password("grace", "Password456!")
    token = reg["session_token"]

    # Session active
    assert auth_mgr.validate_session(token) is not None

    # Revoke (Logout)
    assert auth_mgr.logout(token) is True

    # Session no longer valid
    assert auth_mgr.validate_session(token) is None


# --- 5. HTTP Endpoints API Integration Tests ---

@pytest.fixture(scope="module")
def auth_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_http_auth_full_cycle(auth_server):
    unique_user = f"heidi_{secrets.token_hex(4)}"
    # 1. Register fallback account via HTTP POST
    req = urllib.request.Request(
        f"{auth_server}/api/auth/register/fallback",
        data=json.dumps({"username": unique_user, "password": "PassKeyBackup99!", "displayName": "Heidi"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["success"] is True
        token = data["session_token"]

    # 2. Check session via GET
    s_req = urllib.request.Request(
        f"{auth_server}/api/auth/session",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(s_req) as resp:
        assert resp.status == 200
        s_data = json.loads(resp.read().decode())
        assert s_data["authenticated"] is True
        assert s_data["session"]["username"] == unique_user

    # 3. Log out via POST
    out_req = urllib.request.Request(
        f"{auth_server}/api/auth/logout",
        data=json.dumps({"sessionToken": token}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(out_req) as resp:
        assert resp.status == 200
        out_data = json.loads(resp.read().decode())
        assert out_data["revoked"] is True

    # 4. Verify session is now 401 Unauthorized
    bad_req = urllib.request.Request(
        f"{auth_server}/api/auth/session",
        headers={"Authorization": f"Bearer {token}"}
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(bad_req)
    assert exc_info.value.code == 401
