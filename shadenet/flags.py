#!/usr/bin/env python3
"""Feature Flags Subsystem — ShadeNet (Task 6.6).

Dynamic, zero-restart feature toggles, canary rollout percentages,
and cohort targeting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shadenet.logging import get_logger

logger = get_logger("shadenet.flags")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FLAGS_FILE = ROOT / "state" / "feature_flags.json"
_lock = threading.Lock()

DEFAULT_FLAGS = {
    "ar_camera_portal": {
        "enabled": True,
        "rollout_percentage": 100,
        "cohorts": [],
        "description": "WebXR spatial AR camera overlay for print markers",
    },
    "canary_release": {
        "enabled": False,
        "rollout_percentage": 10,
        "cohorts": ["internal_stewards"],
        "description": "Canary rollout of experimental runtime features",
    },
    "syndicated_summary": {
        "enabled": True,
        "rollout_percentage": 100,
        "cohorts": [],
        "description": "Syndicated daily summary module in hub layout",
    },
    "classifieds_board": {
        "enabled": True,
        "rollout_percentage": 100,
        "cohorts": [],
        "description": "Community classifieds board in market slot",
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FeatureFlagManager:
    def __init__(self, path: Path | None = None):
        self.path = path or DEFAULT_FLAGS_FILE
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._flags: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self):
        with _lock:
            if self.path.exists():
                try:
                    self._flags = json.loads(self.path.read_text(encoding="utf-8"))
                    return
                except Exception as exc:
                    logger.warning("failed_to_load_flags_using_defaults", error=str(exc))
            self._flags = {
                k: {**v, "updated_at": _now_iso()}
                for k, v in DEFAULT_FLAGS.items()
            }
            self._save()

    def _save(self):
        self.path.write_text(json.dumps(self._flags, indent=2), encoding="utf-8")

    def is_enabled(
        self,
        flag_name: str,
        context_id: str | None = None,
        cohort: str | None = None,
    ) -> bool:
        """Evaluate if a flag is active for a given context or cohort."""
        with _lock:
            flag = self._flags.get(flag_name)
            if not flag:
                return False

            if not flag.get("enabled", False):
                return False

            # Check cohort inclusion
            if cohort and cohort in flag.get("cohorts", []):
                return True

            percentage = flag.get("rollout_percentage", 100)
            if percentage >= 100:
                return True
            if percentage <= 0:
                return False

            # Deterministic hash for percentage rollouts
            ctx = context_id or "anonymous_default"
            digest = hashlib.sha256(f"{flag_name}:{ctx}".encode("utf-8")).hexdigest()
            bucket = int(digest[:8], 16) % 100
            return bucket < percentage

    def set_flag(
        self,
        flag_name: str,
        enabled: bool = True,
        rollout_percentage: int = 100,
        cohorts: list[str] | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Update or create a feature flag live."""
        with _lock:
            existing = self._flags.get(flag_name, {})
            record = {
                "enabled": bool(enabled),
                "rollout_percentage": max(0, min(100, int(rollout_percentage))),
                "cohorts": cohorts if cohorts is not None else existing.get("cohorts", []),
                "description": description or existing.get("description", f"Feature flag {flag_name}"),
                "updated_at": _now_iso(),
            }
            self._flags[flag_name] = record
            self._save()

            logger.info(
                "feature_flag_updated",
                flag=flag_name,
                enabled=record["enabled"],
                percentage=record["rollout_percentage"],
            )
            return record

    def get_all_flags(self) -> dict[str, dict[str, Any]]:
        with _lock:
            return dict(self._flags)


# Global singleton manager
_manager = None


def get_manager() -> FeatureFlagManager:
    global _manager
    if _manager is None:
        _manager = FeatureFlagManager()
    return _manager


def is_enabled(flag_name: str, context_id: str | None = None, cohort: str | None = None) -> bool:
    return get_manager().is_enabled(flag_name, context_id=context_id, cohort=cohort)


def set_flag(
    flag_name: str,
    enabled: bool = True,
    rollout_percentage: int = 100,
    cohorts: list[str] | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    return get_manager().set_flag(
        flag_name,
        enabled=enabled,
        rollout_percentage=rollout_percentage,
        cohorts=cohorts,
        description=description,
    )


def get_all_flags() -> dict[str, dict[str, Any]]:
    return get_manager().get_all_flags()


def main():
    parser = argparse.ArgumentParser(description="ShadeNet Feature Flag Manager")
    parser.add_argument("--list", action="store_true", help="List all flags")
    parser.add_argument("--check", help="Check if flag is enabled")
    parser.add_argument("--context", help="Context ID for percentage hash")
    parser.add_argument("--set", help="Flag name to set")
    parser.add_argument("--enable", action="store_true", help="Set flag to enabled")
    parser.add_argument("--disable", action="store_true", help="Set flag to disabled")
    parser.add_argument("--percentage", type=int, default=100, help="Rollout percentage (0-100)")

    args = parser.parse_args()

    if args.check:
        enabled = is_enabled(args.check, context_id=args.context)
        print(f"Flag '{args.check}': {'ENABLED' if enabled else 'DISABLED'}")
    elif args.set:
        status = True if args.enable else (False if args.disable else True)
        res = set_flag(args.set, enabled=status, rollout_percentage=args.percentage)
        print(f"Flag '{args.set}' updated: {res}")
    else:
        flags = get_all_flags()
        print(json.dumps(flags, indent=2))


if __name__ == "__main__":
    main()
