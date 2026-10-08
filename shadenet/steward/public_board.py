#!/usr/bin/env python3
"""
Public board v1 — NightCal v0.2.

Posts via the public A2A endpoint → Gatekeeper triage → rendered board.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).parent))
import command_engine as ce  # noqa: E402

INBOX_URL = "https://a2a-inbox.example.org/api/a2a"
BEARER = os.environ.get("NIGHTCAL_BEARER", "")

VALID_BOARDS = {"general", "events", "venues", "zine"}


class PublicBoard:
    """Public board — posts go through Gatekeeper triage."""

    def __init__(self, agent_address: str = "a2a://agent/board_agent"):
        self.agent_address = agent_address
        self.posts: list[dict] = []
        self.triage_log: list[dict] = []

    def post(self, board: str, body: str, reply_to: str | None = None) -> dict:
        """Submit a post. Returns triage outcome: delivered, quarantined, or rejected."""
        if board not in VALID_BOARDS:
            return {"ok": False, "error": {"code": "schema_invalid", "message": f"board must be one of {sorted(VALID_BOARDS)}"}}

        envelope = ce.make_envelope("board.post", {
            "board": board,
            "body": body,
            **({"replyTo": reply_to} if reply_to else {}),
        }, self.agent_address)

        result = ce.execute(envelope, self.agent_address)
        if result.get("ok"):
            post = result["result"]
            post["board"] = board
            post["body"] = body
            post["replyTo"] = reply_to
            post["triage"] = self._triage(post)
            self.posts.append(post)
            self.triage_log.append(post)
        return result

    def _triage(self, post: dict) -> str:
        """Gatekeeper triage logic — delivered, quarantined, or rejected."""
        body = post.get("body", "")
        board = post.get("board", "")

        # Quarantine rules
        if len(body) > 3000:
            return "quarantined"
        if board == "zine" and not body.strip():
            return "quarantined"

        # Reject rules
        if not body.strip():
            return "rejected"

        return "delivered"

    def get_board(self, board: str) -> list[dict]:
        """Get all delivered posts for a board (excluding quarantined/rejected)."""
        return [p for p in self.posts if p.get("board") == board and p.get("triage") == "delivered"]

    def get_quarantined(self) -> list[dict]:
        """Get quarantined posts — not displayed until human approves."""
        return [p for p in self.posts if p.get("triage") == "quarantined"]


def run_tests() -> Any:
    ce.reset_store()
    tr = type('TR', (), {'passed': 0, 'failed': 0, 'errors': [], 'assert_eq': lambda self, l, a, e: setattr(self, 'passed', self.passed + (a == e)) or print(f"  ✓ {l}") if a == e else (setattr(self, 'failed', self.failed + 1), self.errors.append(f"FAIL {l}"), print(f"  ✗ {l}")), 'assert_ok_true': lambda self, l, r: setattr(self, 'passed', self.passed + (r.get('ok') is True)) or print(f"  ✓ {l}") if r.get('ok') is True else (setattr(self, 'failed', self.failed + 1), self.errors.append(f"FAIL {l}"), print(f"  ✗ {l}")), 'assert_ok_false': lambda self, l, r: setattr(self, 'passed', self.passed + (r.get('ok') is False)) or print(f"  ✓ {l}") if r.get('ok') is False else (setattr(self, 'failed', self.failed + 1), self.errors.append(f"FAIL {l}"), print(f"  ✗ {l}")), 'assert_in': lambda self, l, n, h: setattr(self, 'passed', self.passed + (n in str(h))) or print(f"  ✓ {l}") if n in str(h) else (setattr(self, 'failed', self.failed + 1), self.errors.append(f"FAIL {l}"), print(f"  ✗ {l}"))})()

    print("\n══ Public board v1 tests ══")
    board = PublicBoard(agent_address="a2a://agent/board_agent")

    # --- Delivered posts ---
    r1 = board.post("events", "Show tonight at 9pm")
    tr.assert_ok_true("board.post delivered", r1)

    r2 = board.post("general", "Welcome to NightCal")
    tr.assert_ok_true("board.post general delivered", r2)

    # --- Quarantined (long body) ---
    r3 = board.post("events", "x" * 3500)
    tr.assert_ok_true("board.post quarantined (long body)", r3)
    if r3.get("ok"):
        triage = board._triage({"board": "events", "body": "x" * 3500})
        tr.assert_eq("triage quarantined", triage, "quarantined")

    # --- Rejected (empty body) ---
    r4 = board.post("events", "")
    tr.assert_ok_false("board.post rejected (empty)", r4)

    # --- Invalid board ---
    r5 = board.post("spam", "bad board")
    tr.assert_ok_false("board.post invalid board rejected", r5)

    # --- Get delivered board ---
    delivered = board.get_board("events")
    tr.assert_eq("get_board returns only delivered", len(delivered), 1)

    # --- Quarantined not in delivered ---
    quarantined = board.get_quarantined()
    tr.assert_eq("quarantined posts separated", len(quarantined), 1)

    total = tr.passed + tr.failed
    print(f"\n  Results: {tr.passed}/{total} passed, {tr.failed} failed")
    return tr


def run_live_tests() -> Any:
    tr = type('TR', (), {'passed': 0, 'failed': 0, 'errors': [], 'assert_eq': lambda self, l, a, e: setattr(self, 'passed', self.passed + (a == e)) or print(f"  ✓ {l}") if a == e else (setattr(self, 'failed', self.failed + 1), self.errors.append(f"FAIL {l}"), print(f"  ✗ {l}")), 'assert_ok_true': lambda self, l, r: setattr(self, 'passed', self.passed + (r.get('ok') is True)) or print(f"  ✓ {l}") if r.get('ok') is True else (setattr(self, 'failed', self.failed + 1), self.errors.append(f"FAIL {l}"), print(f"  ✗ {l}")), 'assert_in': lambda self, l, n, h: setattr(self, 'passed', self.passed + (n in str(h))) or print(f"  ✓ {l}") if n in str(h) else (setattr(self, 'failed', self.failed + 1), self.errors.append(f"FAIL {l}"), print(f"  ✗ {l}"))})()

    print("\n══ Live public board tests ══")
    if not BEARER:
        tr.errors.append("SKIP: NIGHTCAL_BEARER not set")
        print("  ⊘ Skipped")
        return tr

    board = PublicBoard(agent_address="a2a://agent/board_live")

    r1 = board.post("events", "Live board post via Hermes")
    tr.assert_ok_true("live board.post", r1)

    # Post via inbox directly
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "SendMessage",
        "params": {"message": {"role": "ROLE_USER", "metadata": {"senderName": "hermes"},
            "parts": [{"kind": "text", "text": json.dumps({"command": "board.post", "args": {"board": "events", "body": "Inbox board post"}, "messageId": "mid_live_1", "idempotencyKey": "ik_live_1", "from": "a2a://agent/board_live", "timestamp": "2026-10-07T04:10:00Z"})}]}}
    }
    try:
        resp = httpx.post(INBOX_URL, json=payload, headers={"Authorization": f"Bearer {BEARER}", "Content-Type": "application/json"}, timeout=15)
        data = resp.json()
        tr.assert_in("inbox accepted board.post", "result", str(data))
    except Exception as exc:
        tr.errors.append(f"inbox post failed: {exc}")

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
        for e in tr.errors:
            print(f"  - {e}")
    sys.exit(0 if tr.failed == 0 else 1)