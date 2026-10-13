"""Tests for Task 6.9: Scheduled Automations & Supervision.

Verifies:
  1. Each automation has an owner, a schedule, and status reporting.
  2. Integration tests forcing each automation to fail in staging and asserting the failure alert:
     - Scraper supervision (login wall / CAPTCHA challenge & error spike)
     - Daily page build failure
     - Summary ingest failure (malformed payload / missing fields)
     - Backup verification failure (checksum mismatch / corrupted database)
  3. Operator console alert dispatch and alert queue tracking.
  4. CLI runner operations (tools/automations.py).
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from shadenet.automations import (
    AutomationFailure,
    AutomationRegistry,
    run_scraper_supervision,
    run_daily_page_build,
    run_summary_ingest,
    run_backup_verification,
)
from shadenet.operator import get_operator_alerts, get_operator_status


@pytest.fixture
def test_registry(tmp_path):
    state_file = tmp_path / "automations_state.json"
    return AutomationRegistry(state_file=state_file)


def test_registry_tasks_metadata(test_registry):
    tasks = test_registry.list_tasks()
    task_map = {t["name"]: t for t in tasks}

    assert "scraper_supervision" in task_map
    assert task_map["scraper_supervision"]["owner"] == "crawler-bot"
    assert "30m" in task_map["scraper_supervision"]["schedule"]

    assert "daily_page_build" in task_map
    assert task_map["daily_page_build"]["owner"] == "publisher"
    assert "00:01" in task_map["daily_page_build"]["schedule"]

    assert "summary_ingest" in task_map
    assert task_map["summary_ingest"]["owner"] == "editor"

    assert "backup_verification" in task_map
    assert task_map["backup_verification"]["owner"] == "backup-daemon"

    assert "umwelt-horizons/writer-run" in task_map
    assert task_map["umwelt-horizons/writer-run"]["owner"] == "umwelt-horizons"
    assert "8h" in task_map["umwelt-horizons/writer-run"]["schedule"]
    assert "umwelt-horizons/editor-run" in task_map
    assert task_map["umwelt-horizons/editor-run"]["owner"] == "umwelt-horizons"


# --- 1. Scraper Supervision Tests ---

def test_scraper_supervision_healthy():
    healthy_status = {
        "status": "idle",
        "last_run": datetime.now(timezone.utc).isoformat(),
        "venues_scraped": 48,
        "spots_discovered": 172,
        "error_count": 0,
    }
    res = run_scraper_supervision(status_override=healthy_status)
    assert res["status"] == "operational"
    assert res["error_count"] == 0


def test_forced_failure_scraper_login_wall(test_registry):
    """[int] Force scraper failure via simulated login wall / CAPTCHA challenge."""
    blocked_status = {
        "status": "blocked",
        "login_wall_detected": True,
        "last_error": "Cloudflare Turnstile challenge (HTTP 403 Forbidden)",
        "error_count": 1,
    }
    
    # Run through registry to test alerting
    res = test_registry.run_task("scraper_supervision", status_override=blocked_status)
    assert res["success"] is False
    assert "login wall" in res["error"].lower() or "challenge" in res["error"].lower()
    assert res["severity"] == "critical"
    assert res["alert"]["owner"] == "crawler-bot"

    # Assert alert dispatched to operator console
    alerts = get_operator_alerts()
    matched = [a for a in alerts if "scraper" in a["type"].lower() and "login wall" in a["details"].lower()]
    assert len(matched) >= 1
    assert matched[0]["severity"] == "critical"


def test_forced_failure_scraper_error_spike(test_registry):
    """[int] Force scraper failure via error rate spike."""
    spiked_status = {
        "status": "failing",
        "error_count": 12,
        "last_error": "Connection reset by peer (12 consecutive failures)",
    }
    res = test_registry.run_task("scraper_supervision", status_override=spiked_status, max_error_count=5)
    assert res["success"] is False
    assert "error spike" in res["error"].lower()


# --- 2. Daily Page Build Tests ---

def test_daily_page_build_healthy():
    res = run_daily_page_build()
    assert res["status"] == "operational"
    assert res["build_verified"] is True


def test_forced_failure_daily_page_build(test_registry):
    """[int] Force daily page build failure and assert operator alert."""
    res = test_registry.run_task("daily_page_build", mock_fail=True)
    assert res["success"] is False
    assert "build failed" in res["error"].lower()
    assert res["severity"] == "critical"

    alerts = get_operator_alerts()
    matched = [a for a in alerts if "daily_page_build" in a["type"]]
    assert len(matched) >= 1


# --- 3. Summary Ingest Tests ---

def test_summary_ingest_healthy():
    payload = {
        "id": "sum-2026-10-09",
        "date": "2026-10-09",
        "title": "Evening Live Music Circuit",
        "summary": "Full overview of local bands and clubs.",
        "items": ["evt-1", "evt-2"],
    }
    res = run_summary_ingest(summary_payload=payload)
    assert res["status"] == "ingested"
    assert res["summary_id"] == "sum-2026-10-09"


def test_forced_failure_summary_ingest_malformed(test_registry):
    """[int] Force summary ingest failure with malformed schema and assert alert."""
    bad_payload = {
        "id": "sum-bad",
        # missing date, title, summary
    }
    res = test_registry.run_task("summary_ingest", summary_payload=bad_payload)
    assert res["success"] is False
    assert "missing required fields" in res["error"].lower()

    alerts = get_operator_alerts()
    matched = [a for a in alerts if "summary_ingest" in a["type"]]
    assert len(matched) >= 1


# --- 4. Backup Verification Tests ---

def test_backup_verification_healthy(tmp_path):
    db_file = tmp_path / "valid_backup.db"
    con = sqlite3.connect(str(db_file))
    con.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, msg TEXT);")
    con.execute("INSERT INTO test (msg) VALUES ('healthy');")
    con.commit()
    con.close()

    res = run_backup_verification(backup_file=db_file)
    assert res["status"] == "verified"
    assert res["integrity_check"] == "ok"


def test_forced_failure_backup_checksum_mismatch(test_registry, tmp_path):
    """[int] Force backup verification failure via sha256 mismatch and assert alert."""
    db_file = tmp_path / "tampered_backup.db"
    manifest_file = tmp_path / "tampered_backup.json"

    # Create valid SQLite database
    con = sqlite3.connect(str(db_file))
    con.execute("CREATE TABLE test (id INTEGER PRIMARY KEY);")
    con.commit()
    con.close()

    # Write manifest with forged / wrong sha256
    manifest_file.write_text(json.dumps({
        "file": str(db_file),
        "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
    }))

    res = test_registry.run_task("backup_verification", backup_file=db_file, manifest_file=manifest_file)
    assert res["success"] is False
    assert "checksum mismatch" in res["error"].lower()

    alerts = get_operator_alerts()
    matched = [a for a in alerts if "backup_verification" in a["type"]]
    assert len(matched) >= 1
    assert "checksum mismatch" in matched[0]["details"].lower()


# --- 5. CLI Tool Execution Tests ---

def test_cli_automations_status():
    proc = subprocess.run(
        [sys.executable, "tools/automations.py", "--status"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "ShadeNet Scheduled Automations" in proc.stdout
    assert "scraper_supervision" in proc.stdout
    assert "backup_verification" in proc.stdout


def test_cli_automations_run_single():
    proc = subprocess.run(
        [sys.executable, "tools/automations.py", "--run", "daily_page_build"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "SUCCESS: daily_page_build completed" in proc.stdout
