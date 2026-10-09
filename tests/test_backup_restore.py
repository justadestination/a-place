"""Test suite for ShadeNet Backup & Restore Subsystem (Task 6.4)."""

import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest
from shadenet.backup import create_backup, rotate_backups, verify_archive
from tools.restore import check_sqlite_integrity, run_restore


@pytest.fixture
def temp_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        db_path = root / "shadenet.db"
        vault_dir = root / "vault"
        data_dir = root / "data"
        backup_dir = root / "backups"
        restore_dir = root / "scratch_restore"

        vault_dir.mkdir(parents=True)
        data_dir.mkdir(parents=True)
        backup_dir.mkdir(parents=True)

        # Seed sample DB
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test_events (id TEXT PRIMARY KEY, title TEXT);")
        conn.execute("INSERT INTO test_events VALUES ('evt_1', 'Night Show');")
        conn.commit()
        conn.close()

        # Seed sample vault note
        (vault_dir / "sample-note.md").write_text("---\ntitle: Sample Note\n---\nHello world\n")

        # Seed sample data json
        (data_dir / "sample.json").write_text(json.dumps({"key": "value"}))

        yield {
            "root": root,
            "db_path": db_path,
            "vault_dir": vault_dir,
            "data_dir": data_dir,
            "backup_dir": backup_dir,
            "restore_dir": restore_dir,
        }


def test_backup_creation_and_manifest(temp_env):
    res = create_backup(
        output_dir=temp_env["backup_dir"],
        db_path=temp_env["db_path"],
        vault_dir=temp_env["vault_dir"],
        data_dir=temp_env["data_dir"],
    )

    assert res["status"] == "SUCCESS"
    archive_path = Path(res["archive_path"])
    checksum_path = Path(res["checksum_path"])

    assert archive_path.exists()
    assert checksum_path.exists()
    assert res["files_count"] >= 3

    # Check manifest content
    mf = res["manifest"]
    assert "shadenet.db" in mf["files"]
    assert mf["files"]["shadenet.db"]["integrity"] == "ok"
    assert "vault/sample-note.md" in mf["files"]
    assert "data/sample.json" in mf["files"]

    # Verify archive structure
    ver = verify_archive(archive_path)
    assert ver["verified"] is True
    assert ver["sha256"] == res["sha256"]


def test_restore_to_scratch_environment(temp_env):
    backup_res = create_backup(
        output_dir=temp_env["backup_dir"],
        db_path=temp_env["db_path"],
        vault_dir=temp_env["vault_dir"],
        data_dir=temp_env["data_dir"],
    )
    archive_path = Path(backup_res["archive_path"])

    # Run restore drill to scratch directory
    restore_report = run_restore(archive_path, temp_env["restore_dir"])

    assert restore_report["status"] == "RESTORE_VERIFIED"
    assert "ok" in restore_report["database_integrity"]

    # Verify database contents
    restored_db = temp_env["restore_dir"] / "shadenet.db"
    assert restored_db.exists()

    conn = sqlite3.connect(str(restored_db))
    rows = conn.execute("SELECT id, title FROM test_events;").fetchall()
    conn.close()
    assert rows == [("evt_1", "Night Show")]

    # Verify content files
    restored_md = temp_env["restore_dir"] / "vault" / "sample-note.md"
    assert restored_md.exists()
    assert "Sample Note" in restored_md.read_text()


def test_restore_detects_corrupted_checksum(temp_env):
    backup_res = create_backup(
        output_dir=temp_env["backup_dir"],
        db_path=temp_env["db_path"],
        vault_dir=temp_env["vault_dir"],
        data_dir=temp_env["data_dir"],
    )
    archive_path = Path(backup_res["archive_path"])

    # Tamper with archive
    with open(archive_path, "ab") as f:
        f.write(b"corrupted_extra_bytes")

    with pytest.raises(ValueError, match="corrupted"):
        run_restore(archive_path, temp_env["restore_dir"])


def test_backup_rotation_pruning(temp_env):
    bdir = temp_env["backup_dir"]
    # Create 5 dummy backup archives
    for i in range(5):
        p = bdir / f"backup_2026100{i}_000000.tar.gz"
        p.write_text(f"dummy {i}")
        (bdir / f"{p.name}.sha256").write_text("dummy sha")

    # Rotate with max_keep = 2
    deleted = rotate_backups(bdir, max_keep=2)
    assert len(deleted) == 3

    remaining = list(bdir.glob("backup_*.tar.gz"))
    assert len(remaining) == 2
