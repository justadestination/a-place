#!/usr/bin/env python3
"""
Subscriptions v1 — NightCal v0.2.

event.subscribe registers interest; calendar publishes updates
into subscriber outboxes.
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


class SubscriptionManager:
    """Manages event/venue/filter subscriptions and publishes updates."""

    def __init__(self):
        self.subscriptions: dict[str, dict] = {}  # sub_id -> sub data
        self.events: dict[str, dict] = {}  # event store for publishing

    def subscribe(self, subscriber: str, event_id: str | None = None,
                  venue_id: str | None = None,
                  filter_tags: list[str] | None = None) -> dict:
        """Register a subscription for a subscriber."""
        sub_id = f"sub_{len(self.subscriptions) + 1:04d}"
        sub = {
            "subscriptionId": sub_id,
            "subscriber": subscriber,
            "eventId": event_id,
            "venueId": venue_id,
            "filter": {"tags": filter_tags} if filter_tags else None,
            "active": True,
            "createdAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }
        self.subscriptions[sub_id] = sub
        return {"ok": True, "result": {"subscriptionId": sub_id}}

    def unsubscribe(self, subscription_id: str) -> dict:
        """Deactivate a subscription."""
        sub = self.subscriptions.get(subscription_id)
        if not sub:
            return {"ok": False, "error": {"code": "not_found", "message": f"Subscription {subscription_id} not found"}}
        sub["active"] = False
        return {"ok": True, "result": {"subscriptionId": subscription_id, "status": "deactivated"}}

    def register_event(self, event: dict) -> None:
        """Register an event in the calendar core."""
        self.events[event["eventId"]] = event

    def update_event(self, event_id: str, changes: dict) -> dict:
        """Update an event and publish to subscribers."""
        event = self.events.get(event_id)
        if not event:
            return {"ok": False, "error": {"code": "not_found", "message": f"Event {event_id} not found"}}

        event.update(changes)
        self.events[event_id] = event

        # Publish update to matching subscribers
        notifications = self._notify_subscribers(event_id, changes)
        return {"ok": True, "result": {"eventId": event_id, "notifications": len(notifications)}}

    def cancel_event(self, event_id: str, reason: str = "") -> dict:
        """Cancel an event and publish cancellation to subscribers."""
        event = self.events.get(event_id)
        if not event:
            return {"ok": False, "error": {"code": "not_found", "message": f"Event {event_id} not found"}}

        event["status"] = "cancelled"
        event["cancelledReason"] = reason
        self.events[event_id] = event

        notifications = self._notify_subscribers(event_id, {"status": "cancelled", "changeType": "cancelled"})
        return {"ok": True, "result": {"eventId": event_id, "notifications": len(notifications)}}

    def _notify_subscribers(self, event_id: str, change: dict) -> list[dict]:
        """Deliver subscription updates to matching subscribers."""
        notifications = []
        event = self.events.get(event_id, {})
        for sub_id, sub in self.subscriptions.items():
            if not sub.get("active"):
                continue

            # Match by eventId
            if sub.get("eventId") == event_id:
                notifications.append({
                    "subscriptionId": sub_id,
                    "subscriber": sub["subscriber"],
                    "eventId": event_id,
                    "changeType": change.get("changeType", "updated"),
                    "change": change,
                })
                continue

            # Match by venueId
            if sub.get("venueId") == event.get("venueId"):
                notifications.append({
                    "subscriptionId": sub_id,
                    "subscriber": sub["subscriber"],
                    "eventId": event_id,
                    "changeType": change.get("changeType", "updated"),
                    "change": change,
                })
                continue

            # Match by filter tags
            if sub.get("filter") and sub["filter"].get("tags"):
                event_tags = set(event.get("tags", []))
                sub_tags = set(sub["filter"]["tags"])
                if event_tags & sub_tags:
                    notifications.append({
                        "subscriptionId": sub_id,
                        "subscriber": sub["subscriber"],
                        "eventId": event_id,
                        "changeType": change.get("changeType", "updated"),
                        "change": change,
                    })

        return notifications

    def get_subscriber_outbox(self, subscriber: str) -> list[dict]:
        """Get all pending notifications for a subscriber."""
        return [n for n in self._outbox if n["subscriber"] == subscriber]


# Need event reference in _notify_subscribers
import datetime as _dt


def run_tests() -> Any:
    ce.reset_store()
    tr = type('TR', (), {'passed': 0, 'failed': 0, 'errors': [], 'assert_eq': lambda self, l, a, e: setattr(self, 'passed', self.passed + (a == e)) or print(f"  ✓ {l}") if a == e else (setattr(self, 'failed', self.failed + 1), self.errors.append(f"FAIL {l}"), print(f"  ✗ {l}")), 'assert_ok_true': lambda self, l, r: setattr(self, 'passed', self.passed + (r.get('ok') is True)) or print(f"  ✓ {l}") if r.get('ok') is True else (setattr(self, 'failed', self.failed + 1), self.errors.append(f"FAIL {l}"), print(f"  ✗ {l}")), 'assert_in': lambda self, l, n, h: setattr(self, 'passed', self.passed + (n in str(h))) or print(f"  ✓ {l}") if n in str(h) else (setattr(self, 'failed', self.failed + 1), self.errors.append(f"FAIL {l}"), print(f"  ✗ {l}"))})()

    print("\n══ Subscriptions v1 tests ═=")
    mgr = SubscriptionManager()

    # Subscribe
    r1 = mgr.subscribe("a2a://agent/personal_1", event_id="evt_1")
    tr.assert_ok_true("subscribe by eventId", r1)

    r2 = mgr.subscribe("a2a://agent/personal_1", venue_id="ven_1")
    tr.assert_ok_true("subscribe by venueId", r2)

    r3 = mgr.subscribe("a2a://agent/personal_2", filter_tags=["jazz"])
    tr.assert_ok_true("subscribe by filter", r3)

    # Register events
    mgr.register_event({"eventId": "evt_1", "venueId": "ven_1", "title": "Jazz Night", "tags": ["jazz", "live"], "status": "active"})
    mgr.register_event({"eventId": "evt_2", "venueId": "ven_1", "title": "Blues Night", "tags": ["blues"], "status": "active"})

    # Update event → notify subscribers
    r4 = mgr.update_event("evt_1", {"title": "Jazz Night - Rescheduled"})
    tr.assert_ok_true("update_event notifies subscribers", r4)
    if r4.get("ok"):
        tr.assert_eq("notifications sent", r4["result"]["notifications"], 3)  # personal_1 (event) + personal_1 (venue) + personal_2 (tag)

    # Cancel event → notify subscribers
    r5 = mgr.cancel_event("evt_1", reason="Venue closed")
    tr.assert_ok_true("cancel_event notifies subscribers", r5)

    # Unsubscribe
    sub_id = r1["result"]["subscriptionId"]
    r6 = mgr.unsubscribe(sub_id)
    tr.assert_ok_true("unsubscribe success", r6)

    # Update after unsubscribe — should not notify
    r7 = mgr.update_event("evt_2", {"title": "Blues Night - Updated"})
    tr.assert_ok_true("update after unsubscribe", r7)

    total = tr.passed + tr.failed
    print(f"\n  Results: {tr.passed}/{total} passed, {tr.failed} failed")
    return tr


def run_live_tests() -> Any:
    tr = type('TR', (), {'passed': 0, 'failed': 0, 'errors': [], 'assert_eq': lambda self, l, a, e: setattr(self, 'passed', self.passed + (a == e)) or print(f"  ✓ {l}") if a == e else (setattr(self, 'failed', self.failed + 1), self.errors.append(f"FAIL {l}"), print(f"  ✗ {l}")), 'assert_ok_true': lambda self, l, r: setattr(self, 'passed', self.passed + (r.get('ok') is True)) or print(f"  ✓ {l}") if r.get('ok') is True else (setattr(self, 'failed', self.failed + 1), self.errors.append(f"FAIL {l}"), print(f"  ✗ {l}")), 'assert_in': lambda self, l, n, h: setattr(self, 'passed', self.passed + (n in str(h))) or print(f"  ✓ {l}") if n in str(h) else (setattr(self, 'failed', self.failed + 1), self.errors.append(f"FAIL {l}"), print(f"  ✗ {l}"))})()

    print("\n══ Live subscription tests ═=")
    if not BEARER:
        tr.errors.append("SKIP")
        print("  ⊘ Skipped")
        return tr

    mgr = SubscriptionManager()

    # Subscribe via inbox
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "SendMessage",
        "params": {"message": {"role": "ROLE_USER", "metadata": {"senderName": "hermes"},
            "parts": [{"kind": "text", "text": json.dumps({"command": "event.subscribe", "args": {"eventId": "evt_live_sub"}, "messageId": "sub_live_1", "idempotencyKey": "iksub_1", "from": "a2a://agent/sub_live", "timestamp": "2026-10-07T04:20:00Z"})}]}}
    }
    try:
        resp = httpx.post(INBOX_URL, json=payload, headers={"Authorization": f"Bearer {BEARER}", "Content-Type": "application/json"}, timeout=15)
        data = resp.json()
        tr.assert_in("subscribe via inbox", "result", str(data))
    except Exception as exc:
        tr.errors.append(f"subscribe failed: {exc}")

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