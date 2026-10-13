# Automations & Supervision Runbook (Task 6.9)

## Overview

ShadeNet uses a background automations and supervisor subsystem (`shadenet/automations.py`) to monitor recurring operational workloads, detect silent failures (such as scraper login walls or corrupt backups), and trigger alerts directly into the operator console (`/operator`) and structured logs (`shadenet.logging`).

---

## 1. Automation Catalog & Owners

| Automation Name | Title | Owner | Schedule | Heuristics & Checks |
| :--- | :--- | :--- | :--- | :--- |
| `scraper_supervision` | Scraper Supervision | `crawler-bot` | Every 30 minutes | Detects login walls (HTTP 403 / anti-bot challenge), CAPTCHAs, error rate spikes (≥5 errors), and staleness (>24h since last scraped event). |
| `daily_page_build` | Daily Calendar Auto-Build | `publisher` | Daily @ 00:01 | Triggers `/today` and `/day/YYYY-MM-DD` static build and asserts `routes.json` integrity and non-empty index output. |
| `summary_ingest` | Editorial & Syndicate Summary Ingest | `editor` | Every 6 hours | Ingests syndicated summaries into the zine graph; validates JSON schema (`id`, `date`, `title`, `summary`, `items`) and node connectivity. |
| `backup_verification` | Backup Integrity Verification | `backup-daemon` | Every 12 hours | Inspects the most recent SQLite online backup; verifies sha256 checksum against manifest and executes `PRAGMA integrity_check;`. |
| `umwelt-horizons/writer-run` | Zine Writer Run | `umwelt-horizons` | Every 8 hours | Hermes cron. A 40% gate picks a persona and prompt, then the writer follows `zine-automation/HANDOFF-WRITER.md`. |
| `umwelt-horizons/editor-run` | Zine Editor Run | `umwelt-horizons` | Every 8 hours, offset 4 hours | Hermes cron. Edits `drafts/` per `zine-automation/HANDOFF-EDITOR.md`. |

---

## 2. Failure Alerting Architecture

When any automation encounters an unhandled exception or failed check:
1. **Operator Console Dispatch**: The error is automatically dispatched to the Operator Console (`/operator`) via `add_operator_alert()`. The alert includes a unique alert ID, automation name, owner, severity (`critical` or `warning`), plain-language reason, and timestamp.
2. **Structured Logging**: An event is logged with `logger.error("automation_failed", ...)` carrying full context for tracing.
3. **State Persistence**: The registry persists consecutive failure counts, error traces, and alert payloads to `shadenet/data/automations_state.json`.

---

## 3. CLI Operations

### Check Status of Automations
```bash
python3 tools/automations.py --status
```
Outputs an ASCII status table:
```
=== ShadeNet Scheduled Automations ===
+---------------------+---------------+--------------+---------+----------+---------------------+
| Automation          | Owner         | Schedule     | Status  | Failures | Last Run            |
+---------------------+---------------+--------------+---------+----------+---------------------+
| scraper_supervision | crawler-bot   | every 30m    | OK      | 0        | 2026-10-09T06:30:00 |
| daily_page_build    | publisher     | daily @ 00:01| OK      | 0        | 2026-10-09T00:01:00 |
| summary_ingest      | editor        | every 6h     | OK      | 0        | 2026-10-09T06:00:00 |
| backup_verification | backup-daemon | every 12h    | OK      | 0        | 2026-10-09T06:00:00 |
+---------------------+---------------+--------------+---------+----------+---------------------+
```

### Run a Specific Automation
```bash
python3 tools/automations.py --run backup_verification
```

### Run All Automations
```bash
python3 tools/automations.py --run-all
```

---

## 4. Incident Response Runbooks

### Scraper Login Wall or CAPTCHA Alert
1. Inspect the alert details in `/operator` or `shadenet/data/operator_state.json`.
2. Check if upstream venue source updated their anti-bot rules or session headers.
3. Rotate scraper user-agent / proxy configuration if blocked by Cloudflare/AWS WAF.

### Backup Checksum or Integrity Failure
1. Immediately run `python3 tools/restore.py --drill` in a staging environment.
2. If the current backup is corrupt, locate the previous valid backup in `shadenet/data/backups/`.
3. Manually trigger a fresh backup: `python3 -c "from shadenet.backup import create_backup; create_backup()"`.
