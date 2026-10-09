# Structured Logging Specification (Task 6.1)

## Architecture

All ShadeNet services emit single-line structured JSON logs to standard output/error and optional service log files.

### Schema

Every log event contains:
```json
{
  "timestamp": "2026-10-09T10:00:00.123456+00:00",
  "level": "INFO|WARNING|ERROR|DEBUG",
  "service": "nightcal|towncrier|serve",
  "trace_id": "a1b2c3d4e5f67890",
  "event": "request_started|request_completed|request_failed|...",
  "path": "/api/events",
  "method": "POST",
  "status_code": 200,
  "latency_ms": 12.4
}
```

On errors, the record includes diagnostic context:
```json
{
  "timestamp": "2026-10-09T10:00:00.543210+00:00",
  "level": "ERROR",
  "service": "nightcal",
  "trace_id": "a1b2c3d4e5f67890",
  "event": "request_failed",
  "error": "Database locked or malformed payload",
  "error_type": "EventWriteError",
  "traceback": "..."
}
```

## Retention Policy

- **Active Operational Logs**: Retained locally for **14 days**.
- **Rotation**: Automated rotation at 50 MB with gzip compression (max 10 archives).
- **Archival**: Rotated logs older than 14 days pruned automatically via cron (`find /var/log/shadenet -mtime +14 -delete`).

## Operator Query Recipes

### 1. Trace a specific request end-to-end:
```bash
jq -c 'select(.trace_id == "a1b2c3d4e5f67890")' /var/log/shadenet/nightcal.log
```

### 2. Find all failed requests in the last hour:
```bash
jq -c 'select(.level == "ERROR" or .status_code >= 400)' /var/log/shadenet/nightcal.log
```

### 3. Check latency percentiles:
```bash
jq -r 'select(.event == "request_completed") | .latency_ms' /var/log/shadenet/nightcal.log
```
