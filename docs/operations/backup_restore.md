# ShadeNet Backup & Restore Drill Runbook (Task 6.4)

## Overview
ShadeNet implements automated, atomic, and checksummed snapshots across all stateful subsystems:
1. **Primary SQLite Database** (`shadenet/data/shadenet.db` via SQLite Online Backup API)
2. **Zine Vault Content** (`shadenet/horizon/vault/*.md`)
3. **Web Data Models & Schemas** (`web/data/*.json`)
4. **Agent & Subsystem Configurations** (`config/`, `shadenet/steward/config/`, `web/site.json`)

---

## 1. Automated Schedule & Retention

### Crontab Schedule
Automated backups run nightly at 03:00 UTC via systemd timer or cron:
```cron
# /etc/cron.d/shadenet-backup
0 3 * * * cd /var/lib/shadenet && python3 -m shadenet.backup --output-dir /var/backups/shadenet --retention 14 >> /var/log/shadenet-backup.log 2>&1
```

### Retention Policy
- Retains rolling 14 days of daily archives.
- Older archives and their matching `.sha256` checksums are automatically pruned during rotation.

---

## 2. Integrity Guarantees

- **No Partial Reads (Tear Prevention)**: Backups utilize SQLite's native `sqlite3_backup` mechanism, streaming pages directly while respecting WAL/reader transactions.
- **Pre-Packaging Integrity Check**: Executes `PRAGMA integrity_check;` on the cloned snapshot before archiving.
- **Cryptographic Manifest**: Every archive contains an internal `manifest.json` detailing the SHA-256 and byte length of every member file.
- **External SHA-256 Checksum**: Every `.tar.gz` archive produces an accompanying `.tar.gz.sha256` digest file.

---

## 3. Disaster Recovery Restore Drill Runbook

To conduct the required quarterly restore drill into a clean scratch environment:

### Step 1: Create Scratch Environment
```bash
SCRATCH_DIR=$(mktemp -d /tmp/shadenet_restore_XXXXXX)
echo "Drill environment: ${SCRATCH_DIR}"
```

### Step 2: Locate Latest Backup Archive
```bash
LATEST_BACKUP=$(ls -t state/backups/backup_*.tar.gz | head -1)
echo "Target archive: ${LATEST_BACKUP}"
```

### Step 3: Run the Restore Verification Tool
```bash
python3 tools/restore.py --archive "${LATEST_BACKUP}" --target-dir "${SCRATCH_DIR}"
```

### Step 4: Validate Restoration Output
The restore tool will:
1. Verify SHA-256 digest against the accompanying `.sha256` file.
2. Extract all assets safely into `${SCRATCH_DIR}`.
3. Validate `PRAGMA integrity_check;` on the restored `shadenet.db`.
4. Validate that each file's SHA-256 matches `manifest.json`.

Expected success output:
```text
=== Restore Drill Completed Successfully ===
Archive: .../state/backups/backup_20261009_045300.tar.gz
Target:  /tmp/shadenet_restore_XXXXXX
DB Check: ok (N objects verified)
Files:   N verified
Time:    0.045s
```

---

## 4. Quarterly Restore Drill Log

| Date | Operator / Agent | Backup Archive | DB Integrity | Content Check | Duration | Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2026-10-09** | Antigravity / Hermes | `backup_20261009_045300.tar.gz` | `ok (verified)` | All SHA-256 matched | `0.048s` | **PASS** |
