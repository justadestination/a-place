---
name: derivee-agent-scaffold
description: Derivee agent scaffold tests and MCP constraints. Canonical copy lives in the towncrier repo.
---

# Derivee agent scaffold

Canonical copy: `/opt/shadenet/towncrier/agent/scaffold/`

The legacy `agent-scaffold/` working tree is archived in `.graveyard/`. Edit the copy in the towncrier repo. This skill describes that copy.

A declarative dual-role (Builder + Researcher) agent: YAML configs are the
source of truth, `mcp-server/server.py` is a thin MCP server (mcp 2.x
`MCPServer`, stdio transport) exposing 5 tools, `mcp-server/logstack.py` is
the logging and structured error stack.

Why this exists, and what is still unfinished, is `agent/ROADMAP.md`.

## Testing

Three suites, all must pass:

```bash
cd /opt/shadenet/towncrier/agent/scaffold
python3 test_scaffold.py      # component tests — the main harness
python3 test_integration.py   # SDK stdio_client, end-to-end over the protocol
python3 test_mcp_client.py    # hand-rolled JSON-RPC client
```

`test_scaffold.py` is a module-level `@T` decorator harness: every test runs
on import, results print at the bottom, exit 1 if any FAIL. Output goes to
stdout. If it appears empty, check stderr for log records.

Set `AGENT_LOG_LEVEL=CRITICAL` to silence log output while debugging a test.

## Configuration

`config/agent.yaml` is the local-first policy. The local model is Ollama at
`http://127.0.0.1:11434`, model `hermes-3-llama-3.1-8b`. Cloud fallback is a
placeholder. Put `CLOUD_API_KEY` in the environment, never in the yaml.

`config/matrix.yaml` is placeholders. The real token is `MATRIX_ACCESS_TOKEN`.
Unset, `matrix_signal` returns ok with `sent=false` and status
`not-configured`. That is an expected state, not a tool failure.

See `.env.example` at the repo root (`../../../.env.example` from this skill).

## Hard-won constraints

- **stdout is the JSON-RPC stream.** Under `mcp.run(transport="stdio")` the SDK
  writes frames to `sys.stdout`. Never `print()` in a handler — use `log.*`,
  which goes to stderr. `install_stdout_guard()` swaps `sys.stdout` to stderr
  and **breaks the transport** (initialize succeeds, everything after hangs).
  It is diagnostic-only, off unless `AGENT_STDOUT_GUARD=1`.
- **`extra=` keys must not collide with LogRecord attributes.** `args`/`name`/`msg`
  make logging raise `KeyError("Attempt to overwrite ... in LogRecord")`, which
  surfaces as a *tool* failure. `level` is NOT reserved (it stores `levelname`) —
  an `extra={"level": "green"}` silently overwrote the JSON severity. Extras are
  namespaced under an `extra` key in `JsonFormatter` so this can't recur.
- **Don't hardcode `protocolVersion`.** Read `LATEST_PROTOCOL_VERSION` from
  `mcp.types.version`; a pinned `2024` gets rejected with -32602.
- **Never `proc.stderr.read()` on a live subprocess** — blocks until EOF. Drain
  on a background thread.

## Error contract

Tools return envelopes from `logstack.ok()` / `logstack.error()`. `ok` reflects
the call, not the outcome: `matrix_signal` returns `ok=True, sent=False,
status=not_configured` when unconfigured, because that is an expected state and
not a tool failure. Real failures return `ok=False` with `error.code` (see
`ErrorCode`) and a `retryable` flag. `sent` is hoisted top-level in both cases.

Never report success for work not actually performed.

See [[no-permanent-deletion]] before removing anything.
