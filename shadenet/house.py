"""The House, as the NightCal server serves it.

One public door for now: operator mail to @dontwastemytime (posted rule R8).
The Steward core is vendored in vendor/steward at a pinned commit
(tools/vendor_steward.py). Everything that can refuse happens in
steward.door before an event exists; a request that passes is filed by the
operator_inbox graph and written to the ledger. Nothing else files mail.

steward_id belongs to the transport. Until Steward signatures are verified
here, every request is the no-Steward web form and steward_id is null,
whatever the sender put in the body.
"""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor" / "steward"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from steward import graph as graphs  # noqa: E402
from steward.catalog import load_catalog  # noqa: E402
from steward.door import operator_mail_event  # noqa: E402
from steward.engine import start, step  # noqa: E402
from steward.ledger import append  # noqa: E402
from steward.policy import load_policy  # noqa: E402
from steward.stamp import SeenMail, StampError  # noqa: E402

RULES_PATH = VENDOR / "policy" / "house_rules.json"
LEDGER_PATH = ROOT / "state" / "house" / "operator_inbox.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class House:
    def __init__(self, ledger: Path = LEDGER_PATH, rules_path: Path = RULES_PATH) -> None:
        self.rules = json.loads(rules_path.read_text(encoding="utf-8"))
        self.catalog = load_catalog(rules_path)
        self.policy = load_policy(rules_path, self.catalog)
        self.inbox = graphs.load("operator_inbox", self.catalog)
        # In memory: a restart forgets mail_ids, but a stamp only lives
        # operator_stamp_max_age_minutes, so the replay window is that long.
        self.seen = SeenMail(self.rules)
        self.ledger = ledger
        self._lock = threading.Lock()

    def operator_mail(self, body: Any, arrived_at: str | None = None) -> tuple[int, dict[str, Any]]:
        """202 {"filed": mail_id}, or 400 {"refused": reason}."""
        if not isinstance(body, dict):
            return 400, {"refused": "request must be a JSON object"}
        request = {"mail": body.get("mail"), "stamp": body.get("stamp"), "steward_id": None}
        at = arrived_at or _now()
        with self._lock:
            try:
                event = operator_mail_event(request, at, self.rules, self.seen)
            except StampError as exc:
                return 400, {"refused": str(exc)}
            opened = start(self.inbox, f"inbox-{event.payload['mail_id']}", {})
            filed = step(self.inbox, opened.instance, event, self.policy, self.catalog.signals)
            self.ledger.parent.mkdir(parents=True, exist_ok=True)
            append(self.ledger, opened.record)
            append(self.ledger, filed.record)
        return 202, {"filed": event.payload["mail_id"]}
