"""Operator Steward — Specialized Site-Operator Steward with Matrix Server Bridge.

Architecture:
  - Second genre of Steward specifically for site operators.
  - Connects to the local Synapse Matrix server (matrix.example.org).
  - Listens in operator control rooms for commands:
      `!status`       — Reports node health, uptime, scraper state, peer lag.
      `!scrape`       — Triggers on-demand downtown venue scrape run.
      `!rotate-keys`  — Initiates cryptographic key rotation drill.
      `!moderation`   — Displays pending flags and queue count.
  - Automatically pushes critical alerts (scraper wall detected, high error rate, pending flags)
    directly to the operator Matrix room.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shadenet.health import check_subsystems
from shadenet.operator import get_operator_status, rotate_active_key
from shadenet.automations import run_scraper_supervision

MATRIX_SERVER_URL = "https://matrix.example.org"
OPERATOR_ROOM_ALIAS = "#shadenet-ops:shady.example.org"


class OperatorSteward:
    """Site-Operator Steward capable of dispatching alerts and responding to commands."""

    def __init__(self, steward_id: str = "steward-operator-main"):
        self.steward_id = steward_id
        self.role = "Site Operator & Node Guardian"

    def process_command(self, cmd_text: str, user: str = "operator") -> dict[str, Any]:
        """Process an operator bot command and return structured response."""
        parts = cmd_text.strip().split()
        if not parts:
            return {"status": "error", "message": "Empty command"}

        cmd = parts[0].lower()

        if cmd in ("!status", "!health"):
            health = check_subsystems()
            op = get_operator_status()
            scraper = op.get("scraper_status", {})
            return {
                "status": "success",
                "message": (
                    f"🟢 Node Status: {health.get('status', 'healthy').upper()}\n"
                    f"Active Key: {op.get('key_management', {}).get('active_key', {}).get('key_id')}\n"
                    f"Scraper: {scraper.get('status', 'idle')} ({scraper.get('spots_discovered', 0)} spots)\n"
                    f"Moderation Queue: {len(op.get('moderation_queue', []))} pending items"
                ),
                "data": {"health": health, "operator": op}
            }

        elif cmd == "!scrape":
            # Simulate or trigger scraper run
            res = run_scraper_supervision()
            return {
                "status": "success",
                "message": f"Scraper supervision executed: {res.get('status', 'ok')}. Error count: {res.get('error_count', 0)}.",
                "data": res
            }

        elif cmd == "!rotate-keys":
            rot = rotate_active_key(operator_identity=f"steward:{user}")
            new_id = rot.get("new_key", {}).get("key_id", "unknown")
            return {
                "status": "success",
                "message": f"🔑 Key rotation drill complete. New active key: `{new_id}`",
                "data": rot
            }

        elif cmd == "!moderation":
            op = get_operator_status()
            q = op.get("moderation_queue", [])
            lines = [f"Pending Moderation Items: {len(q)}"]
            for item in q[:5]:
                lines.append(f"- [{item.get('item_type')}] {item.get('title')}: {item.get('reason')}")
            return {
                "status": "success",
                "message": "\n".join(lines),
                "data": {"queue_count": len(q), "items": q}
            }

        elif cmd == "!help":
            return {
                "status": "success",
                "message": (
                    "Available Operator Commands:\n"
                    "  !status       - Inspect node health, scraper, and peers\n"
                    "  !scrape       - Run supervisor and venue scraper drill\n"
                    "  !rotate-keys  - Rotate active Ed25519 signing key\n"
                    "  !moderation   - Review flagged classifieds & dispatches\n"
                    "  !help         - Show this help menu"
                )
            }

        else:
            return {
                "status": "error",
                "message": f"Unknown command '{cmd}'. Type `!help` for available operations."
            }

    def format_alert_payload(self, title: str, details: str, severity: str = "warning") -> dict[str, Any]:
        """Construct a standardized Matrix event payload for incident alerts."""
        icon = "🚨" if severity == "critical" else "⚠️"
        ts = datetime.now(timezone.utc).isoformat()
        body = f"{icon} [{severity.upper()}] {title}\n{details}\nTimestamp: {ts}"
        return {
            "msgtype": "m.text",
            "body": body,
            "severity": severity,
            "steward_id": self.steward_id,
            "formatted_body": f"<h4>{icon} {title}</h4><p>{details}</p>",
            "format": "org.matrix.custom.html"
        }
