#!/usr/bin/env python3
"""Restore Drill & Verification Tool — ShadeNet (Task 6.4).

Safely extracts and validates a backup archive into a target scratch directory:
  1. Validates external SHA-256 checksum of the archive.
  2. Extracts archive files safely (preventing path traversal).
  3. Validates SQLite PRAGMA integrity_check on the restored database.
  4. Validates each restored file's SHA-256 checksum against manifest.json.
  5. Outputs a structured drill report with timings and verification status.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def check_sqlite_integrity(db_path: Path) -> tuple[bool, str]:
    if not db_path.exists():
        return False, "Database file does not exist"
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        rows = cursor.fetchall()
        cursor.execute("SELECT count(*) FROM sqlite_master;")
        tables = cursor.fetchone()[0]
        conn.close()
        if len(rows) == 1 and rows[0][0] == "ok":
            return True, f"ok ({tables} objects verified)"
        return False, f"Integrity check failed: {rows}"
    except Exception as exc:
        return False, str(exc)


def safe_extract_tar(tar: tarfile.TarFile, target_dir: Path) -> None:
    target_dir = target_dir.resolve()
    for member in tar.getmembers():
        member_path = (target_dir / member.name).resolve()
        if not str(member_path).startswith(str(target_dir)):
            raise SecurityError(f"Attempted path traversal in tar member: {member.name}")
    tar.extractall(path=target_dir)


def run_restore(
    archive_path: Path,
    target_dir: Path,
    verify_checksum: bool = True,
) -> dict[str, Any]:
    t0 = time.time()
    archive_path = archive_path.resolve()
    target_dir = target_dir.resolve()

    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    # 1. External SHA-256 Checksum Verification
    if verify_checksum:
        chk_path = archive_path.parent / f"{archive_path.name}.sha256"
        if chk_path.exists():
            expected = chk_path.read_text(encoding="utf-8").strip().split()[0]
            actual = sha256_file(archive_path)
            if actual != expected:
                raise ValueError(f"Archive checksum corrupted! Expected {expected}, got {actual}")
        else:
            raise FileNotFoundError(f"Checksum file {chk_path} not found for archive")

    target_dir.mkdir(parents=True, exist_ok=True)

    # 2. Extract Archive
    with tarfile.open(archive_path, "r:gz") as tar:
        safe_extract_tar(tar, target_dir)

    # 3. Read Manifest
    manifest_path = target_dir / "manifest.json"
    if not manifest_path.exists():
        raise ValueError("Archive extraction did not yield manifest.json")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_files = manifest.get("files", {})

    # 4. Verify Database Integrity
    db_path = target_dir / "shadenet.db"
    db_verified = False
    db_msg = "Not present in backup"
    if db_path.exists():
        db_verified, db_msg = check_sqlite_integrity(db_path)
        if not db_verified:
            raise RuntimeError(f"Restored database integrity failed: {db_msg}")

    # 5. Verify Each Extracted File's Checksum
    file_checks = {}
    mismatches = []
    for rel_name, meta in manifest_files.items():
        extracted_file = target_dir / rel_name
        if not extracted_file.exists():
            mismatches.append(f"Missing file: {rel_name}")
            continue
        curr_sha = sha256_file(extracted_file)
        if curr_sha != meta["sha256"]:
            mismatches.append(f"Checksum mismatch for {rel_name}: expected {meta['sha256']}, got {curr_sha}")
        file_checks[rel_name] = {"verified": curr_sha == meta["sha256"], "size": extracted_file.stat().st_size}

    if mismatches:
        raise ValueError(f"Restored content failed verification: {'; '.join(mismatches)}")

    duration = time.time() - t0
    report = {
        "status": "RESTORE_VERIFIED",
        "archive": str(archive_path),
        "target_directory": str(target_dir),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database_integrity": db_msg,
        "files_verified_count": len(file_checks),
        "duration_seconds": round(duration, 3),
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="ShadeNet Restore Drill Tool")
    parser.add_argument("--archive", required=True, type=Path, help="Path to backup tar.gz")
    parser.add_argument("--target-dir", required=True, type=Path, help="Directory to restore into")
    parser.add_argument("--no-checksum", action="store_true", help="Skip external sha256 check")

    args = parser.parse_args()
    try:
        report = run_restore(args.archive, args.target_dir, verify_checksum=not args.no_checksum)
        print("=== Restore Drill Completed Successfully ===")
        print(f"Archive: {report['archive']}")
        print(f"Target:  {report['target_directory']}")
        print(f"DB Check: {report['database_integrity']}")
        print(f"Files:   {report['files_verified_count']} verified")
        print(f"Time:    {report['duration_seconds']}s")
    except Exception as exc:
        print(f"RESTORE FAILED: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
