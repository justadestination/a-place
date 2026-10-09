"""Unit and integration tests for Task 4.2: Lost-phone recovery.

Verifies:
  1. Secure PBKDF2-hashed recovery codes generation.
  2. Self-service lost-phone recovery flow without previous device.
  3. Single-use consumption (used recovery codes cannot be replayed).
  4. Abuse resistance: a stranger with just the username cannot recover.
  5. Operator escalation support request logging.
  6. HTTP API endpoints /api/auth/recovery/* integration.
"""

from __future__ import annotations

import json
import secrets
import threading
from http.server import ThreadingHTTPServer
import urllib.request
import urllib.error
from pathlib import Path

import pytest

from shadenet.auth import AuthStore, AuthManager
from shadenet.nightcal.server import Handler


@pytest.fixture
def auth_store(tmp_path):
    db_file = tmp_path / "test_recovery.db"
    return AuthStore(db_path=db_file)


@pytest.fixture
def auth_mgr(auth_store):
    return AuthManager(store=auth_store, rp_id="localhost", rp_name="Test NightCal")


def test_recovery_code_generation_and_storage(auth_mgr, auth_store):
    reg = auth_mgr.register_with_password("mallory", "SafePassword123!", display_name="Mallory")
    user_id = reg["user"]["id"]

    codes = auth_store.generate_recovery_codes(user_id, count=8)
    assert len(codes) == 8
    for c in codes:
        assert len(c) == 14  # xxxx-xxxx-xxxx
        assert c.count("-") == 2

    # Check database status
    status = auth_store.get_recovery_status(user_id)
    assert status["total"] == 8
    assert status["remaining"] == 8


def test_lost_phone_recovery_flow(auth_mgr, auth_store):
    # User creates account with primary device
    reg = auth_mgr.register_with_password("victor", "VictorPass123!", display_name="Victor")
    user_id = reg["user"]["id"]
    codes = auth_store.generate_recovery_codes(user_id, count=4)
    code_to_use = codes[0]

    # Phone is wiped/lost! Victor recovers using only username and recovery code
    recovered = auth_mgr.recover_account("victor", code_to_use, device_info="New Replacement Phone")
    assert recovered["success"] is True
    assert recovered["user"]["username"] == "victor"
    assert "sess_" in recovered["session_token"]

    # Session is immediately active
    sess = auth_mgr.validate_session(recovered["session_token"])
    assert sess is not None
    assert sess["username"] == "victor"

    # Single-use guarantee: the same code CANNOT be reused
    with pytest.raises(ValueError, match="Invalid username or recovery code"):
        auth_mgr.recover_account("victor", code_to_use)

    # Remaining count decremented
    status = auth_store.get_recovery_status(user_id)
    assert status["remaining"] == 3


def test_abuse_stranger_cannot_recover_with_username_only(auth_mgr, auth_store):
    auth_mgr.register_with_password("target_user", "RealPassword456!")

    # 1. Attacker tries empty / blank code
    with pytest.raises(ValueError):
        auth_mgr.recover_account("target_user", "")

    # 2. Attacker tries random guesses
    for guess in ["0000-0000-0000", "aaaa-bbbb-cccc", "1234-5678-9012"]:
        with pytest.raises(ValueError, match="Invalid username or recovery code"):
            auth_mgr.recover_account("target_user", guess)


def test_operator_support_escalation(auth_mgr, auth_store):
    u = auth_mgr.register_with_password("lost_everything", "Pass123!")

    # User lost all codes and submits escalation request
    esc = auth_mgr.submit_escalation(
        username="lost_everything",
        contact_info="lost@example.org",
        notes="Lost phone in river, recovery sheet damaged."
    )
    assert esc["status"] == "pending"
    assert esc["username"] == "lost_everything"
    assert "esc_" in esc["id"]


class RecoveryServerContext:
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


def _req_json(url: str, method: str = "GET", payload: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
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


def test_http_recovery_endpoints(auth_mgr, auth_store, tmp_path):
    with RecoveryServerContext(auth_mgr, tmp_path / "shadenet.db") as ctx:
        base = f"http://127.0.0.1:{ctx.port}"

        # 1. Register user
        code, reg = _req_json(f"{base}/api/auth/register/fallback", method="POST", payload={
            "username": "rec_user",
            "password": "Password77!",
            "displayName": "Recovery Tester"
        })
        assert code == 200
        token = reg["session_token"]

        # 2. Generate recovery codes via HTTP POST
        code, gen_res = _req_json(f"{base}/api/auth/recovery/generate", method="POST", headers={
            "Authorization": f"Bearer {token}"
        })
        assert code == 200
        codes = gen_res["recovery_codes"]
        assert len(codes) == 8

        # 3. Simulate phone loss & recover
        code, rec_res = _req_json(f"{base}/api/auth/recovery/verify", method="POST", payload={
            "username": "rec_user",
            "recoveryCode": codes[0],
            "deviceInfo": "Replacement Pixel 9"
        })
        assert code == 200
        assert rec_res["success"] is True
        new_token = rec_res["session_token"]
        assert new_token != token

        # 4. Verify new token is valid
        code, check_sess = _req_json(f"{base}/api/auth/session", method="GET", headers={
            "Authorization": f"Bearer {new_token}"
        })
        assert code == 200
        assert check_sess["authenticated"] is True

        # 5. Replay attempt with same code fails with 401
        code, replay_res = _req_json(f"{base}/api/auth/recovery/verify", method="POST", payload={
            "username": "rec_user",
            "recoveryCode": codes[0]
        })
        assert code == 401

        # 6. Test escalation endpoint
        code, esc_res = _req_json(f"{base}/api/auth/recovery/escalate", method="POST", payload={
            "username": "rec_user",
            "contact": "tester@domain.tld",
            "notes": "Edge case drill"
        })
        assert code == 200
        assert esc_res["success"] is True
