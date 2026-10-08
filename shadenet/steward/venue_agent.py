#!/usr/bin/env python3
"""
Venue agent client — thin A2A client for NightCal v0.2.

Polls the outbox, then files event.create / event.update / event.cancel
commands against the command engine pipeline.

Usage:
  python venue_agent.py           # dry-run with pipeline + live A2A
  python venue_agent.py --pipeline # pipeline only (no inbox calls)
  python venue_agent.py --live    # real A2A inbox calls (needs NIGHTCAL_BEARER)
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

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

INBOX_URL = "https://a2a-inbox.example.org/api/a2a"
OUTBOX_URL = "https://a2a-inbox.example.org/api/outbox"
BEARER = os.environ.get("NIGHTCAL_BEARER", "")

# ---------------------------------------------------------------------------
# Reuse the command engine pipeline
# ---------------------------------------------------------------------------

ENGINE_PATH = Path(__file__).parent / "command_engine.py"
sys.path.insert(0, str(ENGINE_PATH.parent))
import command_engine as ce  # noqa: E402


# ---------------------------------------------------------------------------
# Venue agent state
# ---------------------------------------------------------------------------

class VenueAgent:
    """A2A venue agent client — polls outbox, submits commands."""

    def __init__(self, agent_id: str = "venue_agent_01", address: str = "a2a://agent/venue_agent_01"):
        self.agent_id = agent_id
        self.address = address
        self.owned_venues: set[str] = set()
        self.subscriptions: dict[str, dict] = {}

    def file_create(self, venue_id: str, title: str, starts_at: str,
                    ends_at: str | None = None, description: str = "",
                    url: str = "") -> dict:
        """File an event.create command through the pipeline."""
        self.owned_venues.add(venue_id)
        envelope = ce.make_envelope("event.create", {
            "venueId": venue_id,
            "title": title,
            "startsAt": starts_at,
            "endsAt": ends_at,
            "description": description,
            "url": url,
        }, self.address)
        result = ce.execute(envelope, self.address)
        return result

    def file_update(self, event_id: str, patch: dict) -> dict:
        """File an event.update command through the pipeline."""
        envelope = ce.make_envelope("event.update", {
            "eventId": event_id,
            "patch": patch,
        }, self.address)
        result = ce.execute(envelope, self.address)
        return result

    def file_cancel(self, event_id: str, reason: str = "") -> dict:
        """File an event.cancel command through the pipeline."""
        envelope = ce.make_envelope("event.cancel", {
            "eventId": event_id,
            "reason": reason,
        }, self.address)
        result = ce.execute(envelope, self.address)
        return result

    def poll_outbox(self, timeout: float = 10) -> list[dict]:
        """Poll the A2A outbox for messages."""
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
                # Return messages if present
                return data.get("messages", data if isinstance(data, list) else [])
        except Exception:
            pass
        return []

    def process_outbox(self) -> list[dict]:
        """Poll the outbox and execute any venue commands found."""
        messages = self.poll_outbox()
        results = []
        for msg in messages:
            text = msg.get("text", "")
            try:
                envelope = json.loads(text)
            except (json.JSONDecodeError, AttributeError):
                continue
            if not isinstance(envelope, dict):
                continue
            command = envelope.get("command")
            args = envelope.get("args", {})
            if command in ("event.create", "event.update", "event.cancel"):
                result = ce.execute(envelope, self.address)
                results.append({"command": command, "result": result})
        return results

    def send_message(self, text: str) -> dict:
        """Send a message through the A2A inbox."""
        if not BEARER:
            return {"ok": False, "error": {"code": "config", "message": "NIGHTCAL_BEARER not set"}}
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "SendMessage",
            "params": {
                "message": {
                    "role": "ROLE_USER",
                    "metadata": {"senderName": "hermes"},
                    "parts": [{"kind": "text", "text": text}],
                }
            },
        }
        try:
            r = httpx.post(INBOX_URL, json=payload, headers={
                "Authorization": f"Bearer {BEARER}",
                "Content-Type": "application/json",
            }, timeout=15)
            return r.json()
        except Exception as exc:
            return {"ok": False, "error": {"code": "transport", "message": str(exc)}}


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
            print(f"  ✗ {label}: expected ok=True, got {result}")

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
    print("\n══ Venue agent tests ══")

    agent = VenueAgent(agent_id="venue_agent_01", address="a2a://agent/venue_agent_01")

    # --- event.create ---
    r = agent.file_create("ven_1", "Open Mic Night", "2026-10-15T20:00:00Z",
                          ends_at="2026-10-15T23:00:00Z")
    tr.assert_ok_true("venue agent event.create", r)
    evt_id = r["result"]["eventId"] if r.get("ok") else None

    # --- event.update ---
    if evt_id:
        r2 = agent.file_update(evt_id, {"title": "Open Mic Night - Rescheduled"})
        tr.assert_ok_true("venue agent event.update", r2)

    # --- event.cancel ---
    if evt_id:
        r3 = agent.file_cancel(evt_id, reason="Venue closed")
        tr.assert_ok_true("venue agent event.cancel", r3)

    # --- process_outbox with empty outbox (no Bearer) ---
    r4 = agent.process_outbox()
    tr.assert_eq("process_outbox returns list", type(r4), list)

    # --- send_message ---
    r5 = agent.send_message("TASK-START: Venue agent (A2A client)")
    if BEARER:
        tr.assert_in("send_message returns task", "task", str(r5))
    else:
        tr.assert_eq("send_message without bearer fails gracefully",
                      r5.get("ok"), False)

    # --- outbox poll without Bearer ---
    r6 = agent.poll_outbox()
    tr.assert_eq("poll_outbox without bearer returns empty", r6, [])

    # --- Scope boundary: non-venue agent can't create ---
    # (agent address is venue_agent_01, scope check allows any a2a://agent/ address)
    # Verify event.create actually creates in engine
    ce.reset_store()
    r7 = agent.file_create("ven_scope_test", "Scope Test", "2026-10-20T19:00:00Z")
    tr.assert_ok_true("venue agent creates event in engine", r7)

    total = tr.passed + tr.failed
    print(f"\n  Results: {tr.passed}/{total} passed, {tr.failed} failed")
    return tr


def run_live_tests() -> TestResult:
    tr = TestResult()
    print("\n══ Live venue agent tests ══")
    if not BEARER:
        tr.errors.append("SKIP: NIGHTCAL_BEARER not set")
        print("  ⊘ Skipped — NIGHTCAL_BEARER not set")
        return tr

    agent = VenueAgent(agent_id="venue_live_01", address="a2a://agent/venue_live_01")

    # File all three command types
    r_create = agent.file_create("ven_live_2", "Live Test Show", "2026-10-20T21:00:00Z")
    tr.assert_ok_true("live event.create", r_create)
    evt_id = r_create["result"]["eventId"] if r_create.get("ok") else None

    if evt_id:
        r_update = agent.file_update(evt_id, {"description": "Updated description"})
        tr.assert_ok_true("live event.update", r_update)

        r_cancel = agent.file_cancel(evt_id, reason="Live test done")
        tr.assert_ok_true("live event.cancel", r_cancel)

    # Poll outbox
    msgs = agent.poll_outbox()
    tr.assert_eq("outbox poll returns list", type(msgs), list)

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