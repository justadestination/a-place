#!/usr/bin/env python3
"""CLI Tool for Zero-Downtime Secret Rotation Drills (Task 6.5)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from shadenet.secret_store import SecretStore


def run_rotation_drill(overlap_seconds: int = 300, operator: str = "drill-operator"):
    store = SecretStore()
    active_before = store.get_active_fleet_key()
    old_secret = active_before["secret"]
    old_key_id = active_before["key_id"]

    print("=== Starting Zero-Downtime Key Rotation Drill ===")
    print(f"Pre-rotation active key: {old_key_id}")

    # Rotate
    t0 = time.time()
    rotate_res = store.rotate_fleet_key(overlap_seconds=overlap_seconds, rotated_by=operator)
    duration = time.time() - t0

    new_active = store.get_active_fleet_key()
    new_secret = new_active["secret"]
    new_key_id = new_active["key_id"]

    print(f"Post-rotation active key: {new_key_id}")
    print(f"Overlap grace window:    {overlap_seconds} seconds")

    # Verification: Both old and new secrets must authenticate successfully
    old_valid = store.verify_fleet_key(old_secret)
    new_valid = store.verify_fleet_key(new_secret)
    random_invalid = not store.verify_fleet_key("invalid-tampered-token")

    if not (old_valid and new_valid and random_invalid):
        print("ROTATION DRILL FAILED: Dual-key validation check failed!", file=sys.stderr)
        sys.exit(1)

    print("Dual-key verification check: PASS")
    print("  - Old key in grace window: VALID (zero downtime for in-flight requests)")
    print("  - New key in active state: VALID (new requests succeed immediately)")
    print("  - Arbitrary token:         REJECTED (security boundary intact)")
    print(f"Drill execution elapsed:    {duration:.4f}s")
    print("=== Zero-Downtime Rotation Drill COMPLETED SUCCESSFULLY ===")


def main():
    parser = argparse.ArgumentParser(description="Zero-Downtime Secret Rotation Tool")
    parser.add_argument("--overlap", type=int, default=300, help="Grace overlap window in seconds")
    parser.add_argument("--operator", default="rotation-drill-runner", help="Operator username/identity")
    args = parser.parse_args()

    run_rotation_drill(overlap_seconds=args.overlap, operator=args.operator)


if __name__ == "__main__":
    main()
