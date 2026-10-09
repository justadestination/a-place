#!/usr/bin/env python3
"""Secrets Management & Zero-Downtime Rotation Subsystem (Task 6.5).

Provides cryptographic secret storage and zero-downtime rotation:
  1. Real secret store on disk with strict 0600 POSIX permissions.
  2. Fleet signing keys (Ed25519 / bearer tokens) and operator secrets.
  3. Overlap / Grace window: old keys remain valid for verification while
     new keys propagate across the fleet mesh, ensuring zero downtime.
  4. Automatic pruning of expired grace keys once rotation completes.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import stat
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from shadenet.logging import get_logger

logger = get_logger("shadenet.secrets")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SECRETS_FILE = ROOT / "state" / "secrets.json"
DEFAULT_OVERLAP_SECONDS = 300  # 5 minute dual-key verification window


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


class SecretStore:
    def __init__(self, path: Path | None = None, default_overlap: int = DEFAULT_OVERLAP_SECONDS):
        self.path = path or DEFAULT_SECRETS_FILE
        self.default_overlap = default_overlap
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._state: dict[str, Any] = {}
        self._load()

    def _ensure_permissions(self):
        """Enforce strict POSIX 0600 (owner read/write only)."""
        if self.path.exists():
            os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)

    def _default_state(self) -> dict[str, Any]:
        initial_fleet_secret = secrets.token_urlsafe(32)
        initial_key_id = f"fleet_{_now_utc().strftime('%Y%m%d')}_{secrets.token_hex(4)}"
        return {
            "version": "1.0",
            "active_fleet_key": {
                "key_id": initial_key_id,
                "secret": initial_fleet_secret,
                "algorithm": "Ed25519",
                "created_at": _now_iso(),
                "status": "active",
            },
            "operator_token": secrets.token_hex(32),
            "webhook_secrets": {},
            "grace_keys": [],
            "history": [],
        }

    def _load(self):
        if self.path.exists():
            try:
                self._state = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("failed_to_load_secrets_fallback_to_default", error=str(e))
                self._state = self._default_state()
                self._save()
        else:
            self._state = self._default_state()
            self._save()
        self._ensure_permissions()

    def _save(self):
        self.path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        self._ensure_permissions()

    def get_active_fleet_key(self) -> dict[str, Any]:
        return self._state.get("active_fleet_key", {})

    def get_operator_token(self) -> str:
        return self._state.get("operator_token", "")

    def prune_expired_grace_keys(self) -> list[str]:
        """Prune keys whose grace window has elapsed."""
        now = _now_utc()
        active_grace = []
        pruned_ids = []

        for k in self._state.get("grace_keys", []):
            try:
                exp = datetime.fromisoformat(k["grace_expires_at"])
                if exp > now:
                    active_grace.append(k)
                else:
                    pruned_ids.append(k["key_id"])
                    # Archive into retired history
                    k["status"] = "retired"
                    self._state.setdefault("history", []).append(k)
            except Exception:
                pruned_ids.append(k.get("key_id", "unknown"))

        if pruned_ids:
            self._state["grace_keys"] = active_grace
            self._save()
            logger.info("grace_keys_pruned", count=len(pruned_ids), key_ids=pruned_ids)

        return pruned_ids

    def rotate_fleet_key(
        self,
        overlap_seconds: int | None = None,
        rotated_by: str = "operator-console",
    ) -> dict[str, Any]:
        """Perform zero-downtime fleet key rotation with dual-key overlap."""
        overlap = overlap_seconds if overlap_seconds is not None else self.default_overlap
        current_key = self._state.get("active_fleet_key", {})

        now = _now_utc()
        grace_expires_at = (now + timedelta(seconds=overlap)).isoformat()

        # 1. Move old key to grace keys
        if current_key:
            grace_entry = {
                **current_key,
                "status": "grace",
                "retired_at": now.isoformat(),
                "grace_expires_at": grace_expires_at,
                "overlap_seconds": overlap,
            }
            self._state.setdefault("grace_keys", []).append(grace_entry)

        # 2. Mint new active fleet key
        new_key_id = f"fleet_{now.strftime('%Y%m%d')}_{secrets.token_hex(4)}"
        new_secret = secrets.token_urlsafe(32)
        new_key = {
            "key_id": new_key_id,
            "secret": new_secret,
            "algorithm": "Ed25519",
            "created_at": now.isoformat(),
            "status": "active",
            "rotated_by": rotated_by,
        }
        self._state["active_fleet_key"] = new_key
        self._save()

        logger.info(
            "fleet_key_rotated",
            old_key_id=current_key.get("key_id"),
            new_key_id=new_key_id,
            overlap_seconds=overlap,
            rotated_by=rotated_by,
        )

        return {
            "status": "ROTATED",
            "old_key_id": current_key.get("key_id"),
            "new_key_id": new_key_id,
            "overlap_seconds": overlap,
            "grace_expires_at": grace_expires_at,
        }

    def verify_fleet_key(self, candidate_secret: str) -> bool:
        """Verify candidate key against active key OR any valid grace key (zero downtime)."""
        if not candidate_secret:
            return False

        # First check active key
        active = self.get_active_fleet_key()
        if active.get("secret") and secrets.compare_digest(active["secret"], candidate_secret):
            return True

        # Second check grace keys (within overlap window)
        now = _now_utc()
        for k in self._state.get("grace_keys", []):
            try:
                exp = datetime.fromisoformat(k["grace_expires_at"])
                if exp > now and k.get("secret") and secrets.compare_digest(k["secret"], candidate_secret):
                    return True
            except Exception:
                continue

        return False

    def get_status(self) -> dict[str, Any]:
        """Retrieve overview of secret store status."""
        self.prune_expired_grace_keys()
        active = self.get_active_fleet_key()
        return {
            "store_file": str(self.path),
            "permissions": oct(self.path.stat().st_mode & 0o777) if self.path.exists() else "none",
            "active_key_id": active.get("key_id"),
            "active_key_created_at": active.get("created_at"),
            "grace_keys_count": len(self._state.get("grace_keys", [])),
            "grace_keys": [
                {
                    "key_id": k["key_id"],
                    "grace_expires_at": k["grace_expires_at"],
                }
                for k in self._state.get("grace_keys", [])
            ],
            "retired_history_count": len(self._state.get("history", [])),
        }


def main():
    parser = argparse.ArgumentParser(description="ShadeNet Secrets Management & Rotation")
    parser.add_argument("--status", action="store_true", help="Print secret store status")
    parser.add_argument("--rotate", action="store_true", help="Rotate fleet signing key")
    parser.add_argument("--overlap", type=int, default=300, help="Grace overlap window in seconds")
    parser.add_argument("--operator", default="cli-operator", help="Operator identity")

    args = parser.parse_args()
    store = SecretStore()

    if args.rotate:
        res = store.rotate_fleet_key(overlap_seconds=args.overlap, rotated_by=args.operator)
        print("=== Fleet Key Rotated ===")
        print(f"Old Key:    {res['old_key_id']}")
        print(f"New Key:    {res['new_key_id']}")
        print(f"Overlap:    {res['overlap_seconds']}s (valid until {res['grace_expires_at']})")
    elif args.status or True:
        status = store.get_status()
        print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
