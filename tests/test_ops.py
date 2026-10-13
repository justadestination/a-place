"""Operator control plane: auth, gating, step-up, audit, settings, workflows."""

from __future__ import annotations

import pytest

from conftest import OPERATOR, OpsClient, fresh_totp, rearm
from shadenet.ops import audit, auth, logs, metrics, ops_dir, settings, steward


# --- primitives -------------------------------------------------------------------

def test_password_hash_roundtrip():
    stored = auth.hash_password("a very long passphrase")
    assert stored.startswith("scrypt$")
    assert auth.check_password("a very long passphrase", stored)
    assert not auth.check_password("wrong", stored)


def test_totp_matches_rfc6238_vector():
    # RFC 6238 appendix B, SHA-1, T=59 -> 94287082 (8 digits); 6-digit form is the last six.
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # base32("12345678901234567890")
    assert auth.totp_now(secret, at=59) == "287082"


def test_weak_operator_password_rejected(ops_env):
    with pytest.raises(ValueError):
        auth.add_operator("shorty", "too-short")


def test_client_ip_trusts_forwarded_for_only_from_local_proxy():
    assert auth.client_ip("127.0.0.1", "203.0.113.9, 203.0.113.21") == "203.0.113.9"
    assert auth.client_ip("198.51.100.4", "203.0.113.9") == "198.51.100.4"


def test_network_allowlist(monkeypatch):
    monkeypatch.setenv("SHADENET_OPS_ALLOW_CIDRS", "203.0.113.0/24")
    assert auth.network_allowed("203.0.113.11")
    assert not auth.network_allowed("203.0.113.9")


# --- login + gating -------------------------------------------------------------------

def test_ops_api_requires_sign_in(live_server):
    c = OpsClient(live_server)
    for path in ("/api/ops/overview", "/api/ops/logs", "/api/ops/settings", "/api/ops/audit"):
        assert c.request("GET", path)[0] == 401, path


def test_door_verify_stays_public(live_server):
    status, _, _ = OpsClient(live_server).request("POST", "/api/operator/door-verify", {})
    assert status == 200


def test_login_needs_totp(live_server, operator_account):
    c = OpsClient(live_server)
    assert c.login(OPERATOR[0], OPERATOR[1], "000000")[0] == 401
    assert c.login(OPERATOR[0], "wrong password", fresh_totp(operator_account["totp_secret"]))[0] == 401
    auth._failures.clear()


def test_totp_code_cannot_be_replayed(live_server, operator_account):
    rearm()
    code = fresh_totp(operator_account["totp_secret"])
    assert OpsClient(live_server).login(*OPERATOR, code)[0] == 200
    assert OpsClient(live_server).login(*OPERATOR, code)[0] == 401
    auth._failures.clear()


def test_lockout_after_repeated_failures(live_server, operator_account):
    auth._failures.clear()
    c = OpsClient(live_server)
    for _ in range(auth.MAX_FAILURES):
        c.login(OPERATOR[0], "nope", "000000")
    rearm()
    status, data = c.login(*OPERATOR, fresh_totp(operator_account["totp_secret"]))
    assert status == 429 and data["retry_after"] > 0
    auth._failures.clear()


def test_session_cookie_is_locked_down(live_server, operator_account):
    rearm()
    c = OpsClient(live_server)
    status, data, headers = c.request("POST", "/api/ops/login", {"username": OPERATOR[0], "password": OPERATOR[1],
                                                                   "totp": fresh_totp(operator_account["totp_secret"])}, auth=False)
    assert status == 200
    cookie = headers["Set-Cookie"]
    for attr in ("__Host-shadenet_ops=", "HttpOnly", "Secure", "SameSite=Strict", "Path=/"):
        assert attr in cookie


def test_mutation_without_csrf_rejected(ops_client):
    status, _, _ = ops_client.request("POST", "/api/ops/settings", {"key": "chat.enabled", "value": False},
                                      headers={"X-Ops-CSRF": "forged"})
    assert status == 403


def test_logout_ends_session(live_server, operator_account):
    rearm()
    c = OpsClient(live_server)
    assert c.login(*OPERATOR, fresh_totp(operator_account["totp_secret"]))[0] == 200
    assert c.request("POST", "/api/ops/logout", {})[0] == 200
    assert c.request("GET", "/api/ops/session")[0] == 401


# --- settings + step-up ------------------------------------------------------------------

def test_plain_setting_change_is_audited(ops_client):
    status, data, _ = ops_client.request("POST", "/api/ops/settings", {"key": "chat.slow_mode_seconds", "value": 15})
    assert status == 200, data
    assert settings.get("chat.slow_mode_seconds") == 15
    assert audit.tail(1)[0]["action"] == "settings.set"


def test_setting_validation(ops_client):
    status, data, _ = ops_client.request("POST", "/api/ops/settings", {"key": "chat.slow_mode_seconds", "value": 99999})
    assert status == 400 and "between" in data["error"]
    assert ops_client.request("POST", "/api/ops/settings", {"key": "nope.nope", "value": 1})[0] == 400


def test_dangerous_setting_needs_step_up(ops_client, operator_account):
    body = {"key": "agegate.mode", "value": "monitor"}
    status, data, _ = ops_client.request("POST", "/api/ops/settings", body)
    assert status == 428 and data["step_up_required"]
    assert settings.get("agegate.mode") == "enforce"
    rearm()
    status, _, _ = ops_client.request("POST", "/api/ops/settings", body,
                                      headers={"X-Ops-Step-Up": fresh_totp(operator_account["totp_secret"])})
    assert status == 200
    assert settings.get("agegate.mode") == "monitor"


# --- workflows -----------------------------------------------------------------------------

def test_recovery_approval_starts_waiting_period(ops_client, operator_account):
    status, data, _ = ops_client.request("POST", "/api/ops/recovery", {
        "account": "someone", "reason": "lost phone",
        "evidence": [{"kind": "in_person", "note": "came to the door"}]})
    assert status == 200, data
    rid = data["result"]["id"]
    assert ops_client.request("POST", f"/api/ops/recovery/{rid}/approve", {})[0] == 428
    rearm()
    status, data, _ = ops_client.request("POST", f"/api/ops/recovery/{rid}/approve", {},
                                         headers={"X-Ops-Step-Up": fresh_totp(operator_account["totp_secret"])})
    assert status == 200, data
    assert data["result"]["status"] == "approved" and data["result"]["executable_after"]
    rearm()
    # Still inside the waiting period, so execution is refused.
    status, data, _ = ops_client.request("POST", f"/api/ops/recovery/{rid}/execute", {},
                                         headers={"X-Ops-Step-Up": fresh_totp(operator_account["totp_secret"])})
    assert status == 400 and "waiting period" in data["error"]


def test_venue_custodians_and_at_risk(ops_client):
    status, data, _ = ops_client.request("GET", "/api/ops/venues")
    assert status == 200
    vid = data["venues"][0]["venue_id"]
    assert data["venues"][0]["at_risk"]
    for acct in ("alice", "bob"):
        assert ops_client.request("POST", "/api/ops/venues/custodians", {"venue_id": vid, "account": acct, "role": "manager"})[0] == 200
    row = next(v for v in ops_client.request("GET", "/api/ops/venues")[1]["venues"] if v["venue_id"] == vid)
    assert not row["at_risk"]


def test_agegate_override_needs_step_up_and_expires(ops_client, operator_account):
    body = {"subject": "door:moonlight", "kind": "grant", "reason": "scanner broken tonight", "days": 1}
    assert ops_client.request("POST", "/api/ops/agegate", body)[0] == 428
    rearm()
    status, data, _ = ops_client.request("POST", "/api/ops/agegate", body,
                                         headers={"X-Ops-Step-Up": fresh_totp(operator_account["totp_secret"])})
    assert status == 200
    from shadenet.ops import agegate
    assert agegate.active_for("door:moonlight")["kind"] == "grant"
    with pytest.raises(ValueError):
        agegate.create("x", "grant", "r", 365, "t")


# --- logs, metrics, steward, audit -----------------------------------------------------------------

def test_logs_read_back_from_file(monkeypatch, tmp_path):
    from shadenet.logging import StructuredLogger
    log = tmp_path / "shadenet.jsonl"
    monkeypatch.setenv("SHADENET_LOG_FILE", str(log))
    lg = StructuredLogger(service="t")
    lg.info("hello", n=1)
    lg.error("scraper_wall", venue="x", trace_id="abc123")
    lg.error("scraper_wall", venue="y")
    res = logs.query(level="ERROR")
    assert res["source"]["kind"] == "file" and res["count"] == 2
    assert logs.query(trace_id="abc123")["records"][0]["venue"] == "x"
    assert logs.error_groups()[0]["count"] == 2


def test_metrics_record_and_group():
    metrics.record("GET", "/api/events/evt_123", 200, 12.0)
    metrics.record("GET", "/api/events/evt_456", 503, 40.0)
    assert metrics.route_group("/api/events/evt_123") == "/api/events"
    assert metrics.route_group("/api/ops/logs") == "/api/ops/logs"
    route = next(r for r in metrics.snapshot()["routes"] if r["route"] == "GET /api/events")
    assert route["count"] >= 2 and route["errors"] >= 1


def test_steward_is_deterministic(ops_env):
    assert "unknown command" in steward.run("please summarise my week", actor="t", stepped_up=False)["text"]
    assert steward.run("help", actor="t", stepped_up=False)["ok"]
    res = steward.run("set agegate.mode off", actor="t", stepped_up=False)
    assert res.get("step_up_required")
    assert steward.run("get chat.enabled", actor="t", stepped_up=False)["ok"]


def test_steward_endpoint(ops_client):
    status, data, _ = ops_client.request("POST", "/api/ops/steward", {"command": "status"})
    assert status == 200 and data["ok"] and "overall" in data["text"]


def test_audit_chain_detects_tampering(ops_env):
    audit.record("t", "test.one")
    audit.record("t", "test.two")
    assert audit.verify()["ok"]
    path = ops_dir() / "audit.jsonl"
    lines = path.read_text().splitlines()
    lines[0] = lines[0].replace('"actor": "', '"actor": "x', 1)
    path.write_text("\n".join(lines) + "\n")
    assert not audit.verify()["ok"]
    path.unlink()
