#!/usr/bin/env python3
"""
Personal agent login — NightCal v0.2.

App/web login granting submit + receive capabilities.
- login: authenticates an agent, returns a session token
- submit: posts to a board (board.post)
- receive: polls outbox for subscription updates

Usage:
  python personal_agent.py           # pipeline + live
  python personal_agent.py --pipeline # pipeline only
  python personal_agent.py --live    # real A2A inbox calls (needs NIGHTCAL_BEARER)
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).parent))
import command_engine as ce  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

INBOX_URL = "https://a2a-inbox.example.org/api/a2a"
OUTBOX_URL = "https://a2a-inbox.example.org/api/outbox"
BEARER = os.environ.get("NIGHTCAL_BEARER", "")

# ---------------------------------------------------------------------------
# Personal agent
# ---------------------------------------------------------------------------

class PersonalAgent:
    """A2A personal agent with login + submit/receive capabilities."""

    def __init__(self, agent_id: str = "personal_agent_01", address: str = "a2a://agent/personal_agent_01"):
        self.agent_id = agent_id
        self.address = address
        self.session_token: str | None = None
        self.logged_in = False
        self.login_time: str | None = None
        self.subscriptions: list[dict] = []

    def login(self, username: str, password: str | None = None) -> dict:
        """Authenticate the personal agent.

        In v1 this is a local session — no server-side session store yet.
        Returns a session token and grants submit + receive scopes.
        """
        if not username:
            return {"ok": False, "error": {"code": "auth_required", "message": "username required"}}

        self.session_token = f"sess_{uuid.uuid4().hex[:16]}"
        self.logged_in = True
        self.login_time = datetime.now(timezone.utc).isoformat()

        return {
            "ok": True,
            "result": {
                "agentId": self.agent_id,
                "address": self.address,
                "sessionToken": self.session_token,
                "scopes": ["submit", "receive"],
                "loginAt": self.login_time,
            },
        }

    def logout(self) -> dict:
        """End the session."""
        self.session_token = None
        self.logged_in = False
        return {"ok": True, "result": {"status": "logged_out"}}

    def submit(self, board: str, body: str, reply_to: str | None = None) -> dict:
        """Submit a board post (requires login)."""
        if not self.logged_in:
            return {"ok": False, "error": {"code": "auth_required", "message": "Not logged in"}}

        args = {"board": board, "body": body}
        if reply_to:
            args["replyTo"] = reply_to

        envelope = ce.make_envelope("board.post", args, self.address)
        result = ce.execute(envelope, self.address)
        return result

    def receive(self, timeout: float = 10) -> list[dict]:
        """Poll the outbox for subscription updates."""
        if not BEARER:
            return []
        try:
            r = httpx.get(
                OUTBOX_URL,
                headers={"Authorization": f"Bearer {BEARER}"},
                timeout=timeout,
            )
            if r.status_code == 200:
                data = r.json()
                return data.get("messages", data if isinstance(data, list) else [])
        except Exception:
            pass
        return []

    def subscribe(self, event_id: str | None = None,
                  venue_id: str | None = None,
                  filter_tags: list[str] | None = None) -> dict:
        """Register a subscription."""
        if not self.logged_in:
            return {"ok": False, "error": {"code": "auth_required", "message": "Not logged in"}}

        args: dict = {}
        if event_id:
            args["eventId"] = event_id
        elif venue_id:
            args["venueId"] = venue_id
        elif filter_tags:
            args["filter"] = {"tags": filter_tags}
        else:
            return {"ok": False, "error": {"code": "schema_invalid", "message": "Provide eventId, venueId, or filter"}}

        envelope = ce.make_envelope("event.subscribe", args, self.address)
        result = ce.execute(envelope, self.address)
        if result.get("ok"):
            sub_id = result["result"].get("subscriptionId")
            self.subscriptions.append({"id": sub_id, **args})
        return result

    def unsubscribe(self, subscription_id: str) -> dict:
        """Deactivate a subscription."""
        if not self.logged_in:
            return {"ok": False, "error": {"code": "auth_required", "message": "Not logged in"}}

        envelope = ce.make_envelope("event.unsubscribe", {"subscriptionId": subscription_id}, self.address)
        result = ce.execute(envelope, self.address)
        if result.get("ok"):
            self.subscriptions = [s for s in self.subscriptions if s["id"] != subscription_id]
        return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def assert_eq(self, label: str, actual, expected):
        if actual == expected:
            self.passed += 1
            print(f"  ✓ {label}")
        else:
            self.failed += 1
            self.errors.append(f"FAIL {label}: expected {expected!r}, got {actual!r}")
            print(f"  ✗ {label}")

    def assert_ok_true(self, label: str, result):
        if result.get("ok") is True:
            self.passed += 1
            print(f"  ✓ {label}")
        else:
            self.failed += 1
            self.errors.append(f"FAIL {label}: expected ok=True, got {result}")
            print(f"  ✗ {label}")

    def assert_ok_false(self, label: str, result):
        if result.get("ok") is False:
            self.passed += 1
            print(f"  ✓ {label}")
        else:
            self.failed += 1
            self.errors.append(f"FAIL {label}: expected ok=False, got {result}")
            print(f"  ✗ {label}")

    def assert_in(self, label: str, needle, haystack):
        if needle in str(haystack):
            self.passed += 1
            print(f"  ✓ {label}")
        else:
            self.failed += 1
            self.errors.append(f"FAIL {label}: {needle!r} not in {haystack!r}")
            print(f"  ✗ {label}")


def run_tests() -> TestResult:
    ce.reset_store()
    tr = TestResult()
    print("\n══ Personal agent tests ══")

    agent = PersonalAgent(agent_id="personal_agent_01", address="a2a://agent/personal_agent_01")

    # --- Not logged in, submit rejected ---
    r0 = agent.submit("events", "Hello from personal agent")
    tr.assert_ok_false("submit without login rejected", r0)
    tr.assert_in("error auth_required", "auth_required", str(r0))

    # --- Login ---
    r_login = agent.login("operator", "not-a-real-password")
    tr.assert_ok_true("login success", r_login)
    if r_login.get("ok"):
        tr.assert_in("session token issued", "sess_", str(r_login["result"].get("sessionToken", "")))
        tr.assert_eq("scopes granted", r_login["result"]["scopes"], ["submit", "receive"])

    # --- Submit board.post ---
    r_sub = agent.submit("events", "Show tonight at 9pm")
    tr.assert_ok_true("submit board.post", r_sub)

    r_reply = agent.submit("events", "Re: show", reply_to="post_abc123")
    tr.assert_ok_true("submit board.post with replyTo", r_reply)

    # --- Subscribe ---
    r_sub1 = agent.subscribe(event_id="evt_test_1")
    tr.assert_ok_true("subscribe by eventId", r_sub1)

    r_sub2 = agent.subscribe(venue_id="ven_1")
    tr.assert_ok_true("subscribe by venueId", r_sub2)

    r_sub3 = agent.subscribe(filter_tags=["jazz", "live"])
    tr.assert_ok_true("subscribe by filter", r_sub3)

    # --- Unsubscribe ---
    sub_ids = [s["id"] for s in agent.subscriptions]
    if sub_ids:
        r_unsub = agent.unsubscribe(sub_ids[0])
        tr.assert_ok_true("unsubscribe success", r_unsub)
        tr.assert_eq("subscription removed", len(agent.subscriptions), len(sub_ids) - 1)

    # --- Logout ---
    r_logout = agent.logout()
    tr.assert_ok_true("logout success", r_logout)
    tr.assert_eq("logged_in cleared", agent.logged_in, False)

    # --- Submit after logout rejected ---
    r_post_logout = agent.submit("events", "Should fail")
    tr.assert_ok_false("submit after logout rejected", r_post_logout)

    # --- Login without username ---
    r_bad = agent.login("")
    tr.assert_ok_false("login without username rejected", r_bad)

    # --- Subscribe without login ---
    agent.logged_in = False
    r_nologin = agent.subscribe(event_id="evt_1")
    tr.assert_ok_false("subscribe without login rejected", r_nologin)

    total = tr.passed + tr.failed
    print(f"\n  Results: {tr.passed}/{total} passed, {tr.failed} failed")
    return tr


def run_live_tests() -> TestResult:
    tr = TestResult()
    print("\n══ Live personal agent tests ══")
    if not BEARER:
        tr.errors.append("SKIP: NIGHTCAL_BEARER not set")
        print("  ⊘ Skipped — NIGHTCAL_BEARER not set")
        return tr

    agent = PersonalAgent(agent_id="personal_live_01", address="a2a://agent/personal_live_01")

    # Login
    r = agent.login("operator_live")
    tr.assert_ok_true("live login", r)

    # Submit via inbox
    r2 = agent.submit("general", "Personal agent posting live")
    tr.assert_ok_true("live board.post", r2)

    # Subscribe via inbox
    r3 = agent.subscribe(event_id="evt_live_test")
    tr.assert_ok_true("live event.subscribe", r3)

    # Receive from outbox
    msgs = agent.receive()
    tr.assert_eq("receive returns list", type(msgs), list)

    total = tr.passed + tr.failed
    print(f"\n  Live results: {tr.passed}/{total} passed, {tr.failed} failed")
    return tr


if __name__ == "__main__":
    tr = run_tests()

    if "--live" in sys.argv:
        tr_live = run_live_tests()
        tr.passed += tr_live.passed
        tr.failed += tr_live.failed
        tr.errors.extend(tr_live.errors)

    if tr.errors:
        print(f"\n  Errors:")
        for e in tr.errors:
            print(f"    - {e}")

    sys.exit(0 if tr.failed == 0 else 1)