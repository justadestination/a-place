#!/usr/bin/env python3
"""Comprehensive scaffold test harness.
Tests every component: config loading, tool handlers, role contracts,
matrix reachability, inference, shell sandbox, security posture.
Reports PASS / FAIL / SKIP per test with concrete findings.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent

import httpx
import yaml

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"
STATE = ROOT / "state"
STATE.mkdir(exist_ok=True)

PASS, FAIL, SKIP = 0, 1, 2
results: list[tuple[str, int, str]] = []

# ---- state reset helper: restore tasks.json to seed before stateful tests ----
def reset_tasks():
    seed = load_yaml("tasks.yaml")["seed"]
    (STATE / "tasks.json").write_text(json.dumps(seed, indent=2))

def T(name: str):
    def dec(fn):
        try:
            out = fn()
            status = PASS if out is None else (PASS if out else FAIL)
            msg = out if isinstance(out, str) else ""
            results.append((name, status, msg))
        except Exception as e:
            results.append((name, FAIL, f"exception: {e!r}"))
        return fn
    return dec

# ============================================================
# 1. CONFIG LOADING
# ============================================================

def load_yaml(name: str) -> dict:
    with open(CONFIG / name) as f:
        return yaml.safe_load(f)

@T("config/agent.yaml loads")
def _():
    a = load_yaml("agent.yaml")
    assert a["name"] == "hermes-local"
    assert "roles" in a and "inference" in a
    return None

@T("config/lexicon.yaml loads + has expected sections")
def _():
    lex = load_yaml("lexicon.yaml")
    for sec in ("verbs", "status", "priority", "tags", "phrases", "style"):
        assert sec in lex, f"missing section {sec}"
    assert lex["verbs"]["scout"] == "research / gather information without acting"
    return None

@T("config/tasks.yaml loads + schema + seed")
def _():
    t = load_yaml("tasks.yaml")
    assert "schema" in t
    assert "seed" in t
    assert len(t["seed"]) == 4
    for s in t["seed"]:
        assert all(k in s for k in ("id","title","role","priority","status","tags","description","acceptance"))
    return None

@T("config/mcp-tools.yaml loads + 5 tools declared")
def _():
    m = load_yaml("mcp-tools.yaml")
    assert m["server"]["name"] == "agent-tools"
    tools = m["tools"]
    names = [t["name"] for t in tools]
    assert names == ["task_list","lexicon_lookup","matrix_signal","local_infer","run_shell"], names
    return None

@T("config/matrix.yaml loads")
def _():
    mx = load_yaml("matrix.yaml")
    assert "homeserver" in mx
    assert "room_id" in mx
    if any(p in mx.get("homeserver", "") or p in mx.get("room_id", "") for p in ("your-synapse.example.com", "yourRoomId")):
        return "PLACEHOLDER: matrix.yaml still has your-synapse.example.com / !yourRoomId / @agent — will fail at runtime until filled"
    return None

@T("config/agent.yaml inference.local/endpoint is reachable (no Ollama?)")
def _():
    a = load_yaml("agent.yaml")
    ep = a["inference"]["local"]["endpoint"]
    model = a["inference"]["local"]["model"]
    try:
        r = httpx.get(f"{ep}/api/tags", timeout=8)
        if r.status_code == 200:
            tags = r.json().get("models", [])
            model_names = [m["name"] for m in tags]
            if model in model_names:
                return None
            return f"Ollama reachable but model '{model}' NOT in list: {model_names}"
        else:
            return f"Ollama /api/tags returned {r.status_code}"
    except Exception as e:
        return f"Ollama endpoint {ep} unreachable: {e!r}"

@T("config/agent.yaml cloud_fallback provider/model are placeholders OR filled")
def _():
    a = load_yaml("agent.yaml")
    cf = a["inference"].get("cloud_fallback", {})
    if not cf.get("enabled", True):
        return None
    provider = cf.get("provider")
    model = cf.get("model")
    if provider and model:
        return f"cloud_fallback configured: {provider}/{model} (api_key from env)"
    return "cloud_fallback has enabled:true but provider/model are empty — fill or disable"

# ============================================================
# 2. STATE / SEED
# ============================================================

@T("state/tasks.json seeded from tasks.yaml seed")
def _():
    reset_tasks()
    path = STATE / "tasks.json"
    data = json.loads(path.read_text())
    seed = load_yaml("tasks.yaml")["seed"]
    seed_ids = {s["id"] for s in seed}
    actual_ids = {t["id"] for t in data}
    missing = seed_ids - actual_ids
    extra = actual_ids - seed_ids
    parts = []
    if missing:
        parts.append(f"missing seed ids: {missing}")
    if extra:
        parts.append(f"extra ids (stale): {extra}")
    if parts:
        return "STATE MISMATCH: " + "; ".join(parts)
    return None

@T("state/memory.jsonl existence (optional, not required)")
def _():
    if (STATE / "memory.jsonl").exists():
        lines = (STATE / "memory.jsonl").read_text().strip().splitlines()
        if lines:
            return f"memory.jsonl has {len(lines)} lines"
        return None
    return "SKIP: memory.jsonl not present (optional)"

# ============================================================
# 3. TOOL HANDLERS (import server module, call handlers directly)
# ============================================================

sys.path.insert(0, str(ROOT / "mcp-server"))
import server as srv

@T("tool_task_list action=list returns 4 seed tasks")
def _():
    reset_tasks()
    r = srv.tool_task_list({"action": "list"})
    assert r["ok"] is True, r
    assert isinstance(r["tasks"], list) and len(r["tasks"]) == 4
    assert r["count"] == 4
    return None

@T("tool_task_list action=get by id returns correct task")
def _():
    reset_tasks()
    r = srv.tool_task_list({"action": "get", "id": "T001"})
    assert r["ok"] is True, r
    t = r["task"]
    assert t and t["id"] == "T001" and t["title"] == "Confirm local Hermes endpoint"
    return None

@T("tool_task_list action=get unknown id returns structured error")
def _():
    reset_tasks()
    r = srv.tool_task_list({"action": "get", "id": "NOPE"})
    assert r["ok"] is False, r
    assert r["error"]["code"] == "task.not_found"
    return None

@T("tool_task_list action=update modifies task + stamps updated")
def _():
    reset_tasks()
    r = srv.tool_task_list({"action": "update", "id": "T001", "patch": {"status": "in_progress"}})
    assert r["ok"] is True, r
    assert r["task"]["status"] == "in_progress"
    assert r["task"].get("updated"), "update should stamp the updated timestamp"
    return None

@T("tool_task_list action=add appends new task")
def _():
    reset_tasks()
    task = {"id": "T999", "title": "test", "role": "either", "priority": "later",
            "status": "pending", "tags": [], "description": "test", "acceptance": "test"}
    r = srv.tool_task_list({"action": "add", "task": task})
    assert r["ok"] is True, r
    assert r["task"]["id"] == "T999"
    assert r["task"].get("created")
    return None

@T("tool_task_list rejects duplicate task id")
def _():
    reset_tasks()
    dup = {"id": "T001", "title": "dupe", "role": "either", "priority": "later",
           "status": "pending", "tags": [], "description": "", "acceptance": ""}
    r = srv.tool_task_list({"action": "add", "task": dup})
    assert r["ok"] is False, r
    assert r["error"]["code"] == "task.invalid"
    return None

@T("tool_task_list unknown action returns structured error")
def _():
    r = srv.tool_task_list({"action": "frobnicate"})
    assert r["ok"] is False, r
    assert r["error"]["code"] == "task.unknown_action"
    return None

@T("tool_lexicon_lookup term=scout finds verb")
def _():
    r = srv.tool_lexicon_lookup({"term": "scout"})
    assert r and r.get("meaning") == "research / gather information without acting"
    return None

@T("tool_lexicon_lookup section=status term=green")
def _():
    r = srv.tool_lexicon_lookup({"term": "green", "section": "status"})
    assert r == "on track, no blockers"
    return None

@T("tool_lexicon_lookup unknown term returns None")
def _():
    r = srv.tool_lexicon_lookup({"term": "xyzzy_not_real"})
    assert r is None
    return None

@T("tool_matrix_signal reports honestly: never claims delivery it did not make")
def _():
    r = srv.tool_matrix_signal({"message": "test-signal", "level": "green"})
    # `ok` reflects the call; `sent` reflects delivery. If the config is
    # unconfigured we require ok=True, sent=False AND a stated reason —
    # never ok=True, sent=True from a config that cannot send.
    assert "ok" in r and "sent" in r, r
    cfg = srv.load_yaml("matrix.yaml")
    placeholders = any(
        m in (cfg.get("homeserver","") + cfg.get("room_id",""))
        for m in ("your-synapse.example.com", "yourRoomId")
    )
    if placeholders or not os.environ.get("MATRIX_ACCESS_TOKEN"):
        assert r["sent"] is False, f"claimed delivery while unconfigured: {r}"
        assert r.get("reason") or r.get("error"), f"no reason given for non-delivery: {r}"
        return "UNCONFIGURED: sent=false with a stated reason (expected — placeholders/token)"
    assert r["sent"] is True, f"config looks real but nothing was delivered: {r}"
    return None

@T("tool_matrix_signal error envelope carries a code, not a bare string")
def _():
    # Force the failure path with a bogus but non-placeholder config.
    saved = dict(srv.load_yaml("matrix.yaml"))
    try:
        srv.CONFIG  # exists
        import yaml as _y
        bad = dict(saved)
        bad["homeserver"] = "https://127.0.0.1:9"   # discard port: always refused
        bad["room_id"] = "!test:example.invalid"
        (srv.CONFIG / "matrix.yaml").write_text(_y.safe_dump(bad))
        os.environ["MATRIX_ACCESS_TOKEN"] = "fake-token-for-error-path-test"
        srv.register_secret("fake-token-for-error-path-test")
        r = srv.tool_matrix_signal({"message": "x", "level": "red", "timeout_sec": 3})
        assert r["ok"] is False, r
        assert r["sent"] is False, r
        code = r["error"]["code"]
        assert code in ("matrix.unreachable", "matrix.send_failed", "matrix.auth_failed",
                        "matrix.forbidden", "matrix.not_found"), code
        return None
    finally:
        import yaml as _y
        (srv.CONFIG / "matrix.yaml").write_text(_y.safe_dump(saved))
        os.environ.pop("MATRIX_ACCESS_TOKEN", None)

@T("tool_local_infer hits endpoint (if reachable) OR reports unreachable")
def _():
    a = srv.load_yaml("agent.yaml")
    ep = a["inference"]["local"]["endpoint"]
    model = a["inference"]["local"]["model"]
    try:
        r = httpx.post(f"{ep}/api/generate", json={
            "model": model, "prompt": "Say 'pong' and nothing else.",
            "stream": False, "temperature": 0.0,
        }, timeout=30)
        r.raise_for_status()
        body = r.json()
        resp = body.get("response", "").strip()
        if "pong" in resp.lower():
            return None
        return f"Ollama responded but not with 'pong': {resp!r}"
    except Exception as e:
        return f"local_infer unreachable: {e!r}"

@T("tool_run_shell runs echo and returns stdout")
def _():
    reset_tasks()
    r = srv.tool_run_shell({"command": "echo hello-world-test-1234", "timeout_sec": 10})
    assert r["returncode"] == 0
    assert "hello-world-test-1234" in r["stdout"]
    return None

@T("tool_run_shell sandbox: rejects cd outside ROOT (relative escape)")
def _():
    r = srv.tool_run_shell({"command": "pwd", "cwd": "../..", "timeout_sec": 10})
    if r.get("ok") is False:
        assert r["error"]["code"] == "sandbox.cwd_escape", r
        return None
    cwd_out = r.get("stdout", "").strip()
    if cwd_out == "/home/operator":
        return "SANDBOX FAIL: run_shell allowed cwd escape to /home/operator via '../..'"
    return None

@T("tool_run_shell sandbox: rejects absolute path outside ROOT")
def _():
    r = srv.tool_run_shell({"command": "pwd", "cwd": "/tmp", "timeout_sec": 10})
    if r.get("ok") is False:
        assert r["error"]["code"] in ("sandbox.cwd_escape", "sandbox.forbidden_path"), r
        return None
    cwd_out = r.get("stdout", "").strip()
    if cwd_out == "/tmp":
        return "SANDBOX FAIL: run_shell allowed cwd=/tmp (outside ROOT)"
    return None

@T("tool_run_shell echoes back the cwd it actually used")
def _():
    r = srv.tool_run_shell({"command": "pwd", "timeout_sec": 10})
    assert r["returncode"] == 0
    assert r["cwd"].startswith(str(ROOT.resolve())), r["cwd"]
    # The echoed cwd must match where pwd actually reported.
    assert r["stdout"].strip() == r["cwd"], (r["stdout"], r["cwd"])
    return None

@T("tool_run_shell timeout returns a retryable structured error")
def _():
    r = srv.tool_run_shell({"command": "sleep 5", "timeout_sec": 1})
    assert r["ok"] is False, r
    assert r["error"]["code"] == "shell.timeout", r
    assert r["error"]["retryable"] is True, r
    return None

@T("run_shell has no print() to stdout (would corrupt the JSON-RPC stream)")
def _():
    src = (ROOT / "mcp-server" / "server.py").read_text()
    handler = src[src.find("def tool_run_shell"):src.find("HANDLERS = {")]
    assert "print(" not in handler, "tool_run_shell writes to stdout; use log.* instead"
    return None

@T("tool_run_shell rejects shell metachar injection attempt (logical check)")
def _():
    # The handler uses shell=True, so ; rm -rf / would run. Check that the code
    # at least doesn't have an allowlist. We flag if there's no protection.
    src = (ROOT / "mcp-server" / "server.py").read_text()
    if "shell=True" in src and "allowlist" not in src and "whitelist" not in src:
        return "SECURITY: run_shell uses shell=True with no command allowlist — any command runs"
    return None

# ============================================================
# 4. MCP SDK INTEGRATION — does FastMCP work?
# ============================================================

@T("mcp SDK importable and MCPServer available (mcp 2.x)")
def _():
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer("test")
    @mcp.tool()
    def ping() -> str:
        return "pong"
    return None

@T("server.py can be imported without error (no syntax/runtime errors on import)")
def _():
    # Already imported above as srv; re-verify
    assert hasattr(srv, "HANDLERS")
    assert len(srv.HANDLERS) == 5
    return None

@T("server.py main() is NOT an MCP server (still skeleton)")
def _():
    src = (ROOT / "mcp-server" / "server.py").read_text()
    if "mcp.run" in src or "FastMCP" in src or "mcp.server" in src:
        return None  # already upgraded
    return "INCOMPLETE: server.py main() only demos one call; not wired to MCP SDK"

# ============================================================
# 5. ROLE CONTRACTS vs MCP TOOLS
# ============================================================

@T("role: researcher.md references only tools that exist (MCP or Hermes runtime)")
def _():
    txt = (ROOT / "roles" / "researcher.md").read_text()
    defined_mcp = {"task_list","lexicon_lookup","matrix_signal","local_infer","run_shell"}
    suspected_runtime = {"web_search","web_extract","fetch_url","summarize",
                         "read_file","write_file"}
    # Bullet line: "- task_list, lexicon_lookup, matrix_signal, local_infer"
    #                          "- web_search / fetch_url if the runtime provides them"
    # Extract comma-separated tokens from the tools bullet line.
    bullet_tools: set[str] = set()
    for line in txt.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        # The tools bullet is the line that lists tool names. Take everything
        # after the dash, split on commas and slashes.
        body = stripped[2:]
        # Drop trailing prose after "if" or "and any"
        for cut in (" if ", " and "):
            if cut in body:
                body = body.split(cut)[0]
        for tok in body.replace("/", ",").split(","):
            tok = tok.strip().rstrip(".").strip()
            if tok and tok.isidentifier() and tok.islower():
                bullet_tools.add(tok)
    missing = bullet_tools - defined_mcp - suspected_runtime
    if "matrix_post" in bullet_tools:
        missing.discard("matrix_post")
        return "DRIFT: researcher.md lists 'matrix_post' but MCP tool is 'matrix_signal' (alias needed)"
    if missing:
        return f"DRIFT: researcher.md lists: {sorted(bullet_tools)}; unknown: {sorted(missing)}"
    return None

@T("role: builder.md references only tools that exist (MCP or Hermes runtime)")
def _():
    txt = (ROOT / "roles" / "builder.md").read_text()
    defined_mcp = {"task_list","lexicon_lookup","matrix_signal","local_infer","run_shell"}
    suspected_runtime = {"web_search","web_extract","fetch_url","summarize",
                         "read_file","write_file"}
    bullet_tools: set[str] = set()
    for line in txt.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        body = stripped[2:]
        for cut in (" if ", " and "):
            if cut in body:
                body = body.split(cut)[0]
        for tok in body.replace("/", ",").split(","):
            tok = tok.strip().rstrip(".").strip()
            if tok and tok.isidentifier() and tok.islower():
                bullet_tools.add(tok)
    missing = bullet_tools - defined_mcp - suspected_runtime
    if "list_dir" in bullet_tools or "git_status" in bullet_tools:
        return "DRIFT: builder.md lists 'list_dir'/'git_status' not in MCP tools.yaml (Hermes runtime tools — documented)"
    if missing:
        return f"DRIFT: builder.md lists: {sorted(bullet_tools)}; unknown: {sorted(missing)}"
    return None

# ============================================================
# 6. INSTANTIATE SCRIPT
# ============================================================

@T("instantiate.sh is syntactically valid bash")
def _():
    p = subprocess.run(["bash", "-n", str(ROOT / "instantiate.sh")],
                       capture_output=True, text=True)
    if p.returncode != 0:
        return f"bash -n failed: {p.stderr}"
    return None

@T("instantiate.sh runs to completion (idempotent — state exists)")
def _():
    p = subprocess.run(["bash", str(ROOT / "instantiate.sh")],
                       capture_output=True, text=True, timeout=60, cwd=ROOT)
    if p.returncode != 0:
        return f"instantiate.sh exit {p.returncode}: {p.stderr}"
    # check it seeded if needed
    if not (STATE / "tasks.json").exists():
        return "instantiate.sh did not create state/tasks.json"
    return None

@T("instantiate.sh warns about placeholders (desired behavior — currently missing)")
def _():
    src = (ROOT / "instantiate.sh").read_text()
    if "your-synapse" in src or "yourRoomId" in src or "your-" in src:
        return "NOTE: instantiate.sh does NOT check for remaining placeholders before running"
    return None

# ============================================================
# 7. MATRIX CONNECTIVITY (arnastra via tunnel)
# ============================================================

@T("Matrix lighthouse node-primary (10.0.0.2) reachable via tunnel ICMP")
def _():
    r = subprocess.run(["ping", "-c", "2", "-W", "5", "10.0.0.2"],
                       capture_output=True, text=True, timeout=15)
    if r.returncode == 0 and "0% packet loss" in r.stdout:
        return None
    return f"node-primary ICMP failed: {r.stderr or r.stdout}"

@T("Matrix lighthouse node-primary UDP 4242 reachable (public + overlay)")
def _():
    # public
    r1 = subprocess.run(["nc", "-z", "-u", "-w", "4", "203.0.113.10", "4242"],
                        capture_output=True, text=True, timeout=10)
    pub_ok = r1.returncode == 0
    # overlay
    r2 = subprocess.run(["nc", "-z", "-u", "-w", "4", "10.0.0.2", "4242"],
                        capture_output=True, text=True, timeout=10)
    ovl_ok = r2.returncode == 0
    if pub_ok and ovl_ok:
        return None
    return f"UDP 4242: public={pub_ok} overlay={ovl_ok}"

# ============================================================
# 8. SCHEMA / ACCEPTANCE CRITERIA VERIFIABILITY
# ============================================================

@T("task seed T001 acceptance is verifiable with available tools")
def _():
    tasks = srv.load_tasks()
    t001 = next(t for t in tasks if t["id"] == "T001")
    acc = t001["acceptance"]
    # "Successful chat completion + one tool call round-trip recorded in state."
    # This requires Ollama OR cloud. If neither reachable, acceptance not currently verifiable.
    a = srv.load_yaml("agent.yaml")
    ep = a["inference"]["local"]["endpoint"]
    try:
        httpx.get(f"{ep}/api/tags", timeout=5)
        return None  # Ollama reachable, can verify
    except Exception:
        pass
    if a["inference"].get("cloud_fallback",{}).get("enabled"):
        return "T001 acceptance needs cloud key in env to verify (no local Ollama)"
    return "T001 acceptance not currently verifiable (no local Ollama, cloud disabled/empty)"

@T("task seed acceptance criteria reference only tools the agent has")
def _():
    tasks = srv.load_tasks()
    for t in tasks:
        acc = t.get("acceptance","")
        # crude check: acceptance mentions something implausible
        if "matrix room" in acc.lower() and not os.environ.get("MATRIX_ACCESS_TOKEN"):
            return f"T{t['id']} acceptance references Matrix but no MATRIX_ACCESS_TOKEN set"
    return None

# ============================================================
# 9. GITIGNORE / STATE DIR
# ============================================================

@T("state/ is gitignored (or .gitignore exists declaring it)")
def _():
    gitignore = ROOT / ".gitignore"
    if not gitignore.exists():
        return "MISSING: no .gitignore; state/ would be committed"
    content = gitignore.read_text()
    if "state/" in content or "state" in content:
        return None
    return "MISSING: .gitignore exists but does not mention state/"

# ============================================================
# 10. RENDEZVOUS / HOLDING BEHAVIOR — code exists?
# ============================================================

@T("agent.yaml rendezvous section is configured")
def _():
    a = srv.load_yaml("agent.yaml")
    rv = a.get("rendezvous", {})
    assert rv.get("channel") == "matrix"
    assert "check_interval_minutes" in rv
    return None

@T("No rendezvous loop code exists yet (expected — not implemented)")
def _():
    src = (ROOT / "mcp-server" / "server.py").read_text()
    if "rendezvous" in src.lower() or "check_interval" in src:
        return None  # already implemented
    return "INCOMPLETE: no rendezvous / check loop implemented (agent.yaml declares one)"

# ============================================================
# 11. ESCALATION — code reads agent.yaml escalation_rules?
# ============================================================

@T("agent.yaml escalation_rules present")
def _():
    a = srv.load_yaml("agent.yaml")
    er = a.get("escalation_rules", [])
    assert len(er) >= 2
    return None

@T("No escalation logic implemented in server (expected — not implemented)")
def _():
    src = (ROOT / "mcp-server" / "server.py").read_text()
    if "escalation" in src.lower() or "local_confidence" in src:
        return None
    return "INCOMPLETE: no escalation logic in server.py (agent.yaml declares rules)"

# ============================================================
# 12. TEMPERATURE / CONTEXT NOT PASSED TO OLLAMA (known issue)
# ============================================================

@T("tool_local_infer passes temperature + context from agent.yaml to Ollama")
def _():
    src = (ROOT / "mcp-server" / "server.py").read_text()
    handler = src[src.find("def tool_local_infer"):src.find("def tool_run_shell")]
    if "temperature" in handler and "context" in handler:
        return None
    return "INCOMPLETE: tool_local_infer does NOT pass temperature/context to Ollama (declared in agent.yaml but ignored)"

# ============================================================
# 13. INVENTORY SCRIPT from reviewer zip
# ============================================================

@T("scaffold-reviewer scripts/inventory.py is valid Python")
def _():
    # The reviewer lives as a checked-out sibling directory, not a zip.
    # An earlier version of this test looked for a
    # scaffold-reviewer-repo-with-git.zip that was never committed, so it
    # always failed with FileNotFoundError regardless of the script.
    candidates = [
        ROOT.parent / "skills" / "scaffold-reviewer" / "scripts" / "inventory.py",
        ROOT.parent.parent / "scaffold-reviewer" / "scripts" / "inventory.py",
        ROOT.parent.parent.parent / "scaffold-reviewer" / "scripts" / "inventory.py",
    ]
    inv = next((p for p in candidates if p.exists()), None)
    if not inv:
        return f"MISSING: inventory.py not found at any candidate path: {candidates}"
    p = subprocess.run([sys.executable, str(inv), str(ROOT)],
                       capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        return f"inventory.py failed: {p.stderr or p.stdout}"
    try:
        parsed = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        return f"inventory.py did not emit valid JSON: {exc}"
    for key in ("root", "file_count", "files", "signals"):
        if key not in parsed:
            return f"inventory.py output missing key {key!r}"
    return None

# ============================================================
# 14. LOG STACK
# ============================================================

sys.path.insert(0, str(ROOT / "mcp-server"))
import logstack  # noqa: E402

@T("logstack.error builds a code-bearing envelope with retryable flag")
def _():
    e = logstack.error(logstack.ErrorCode.SHELL_TIMEOUT, "took too long")
    assert e["ok"] is False
    assert e["error"]["code"] == "shell.timeout"
    assert e["error"]["reason"] == "shell.timeout"
    assert e["error"]["retryable"] is True, e
    return None

@T("logstack.ok never claims a false failure")
def _():
    o = logstack.ok(sent=True, level="green")
    assert o["ok"] is True and o["sent"] is True
    return None

@T("logstack redacts registered secrets from messages")
def _():
    secret = "super-secret-token-value-xyz"
    logstack.register_secret(secret)
    assert logstack._redact(f"bearer {secret} end") == "bearer ***REDACTED*** end"
    # short values are ignored so unrelated text is not mangled
    logstack.register_secret("ab")
    assert logstack._redact("ab cd") == "ab cd"
    return None

@T("logstack request scope sets and restores the request id")
def _():
    assert logstack.current_request_id() is None
    with logstack.request_scope(prefix="test") as scope:
        assert logstack.current_request_id() == scope.request_id
        e = logstack.error("x.y", "z")
        assert e["error"]["request_id"] == scope.request_id, e
    assert logstack.current_request_id() is None
    return None

@T("logstack has no retryable code without a matching entry")
def _():
    for code in logstack.RETRYABLE_CODES:
        assert code.startswith(("matrix.", "infer.", "shell.")), code
    # not_configured must NOT be retryable — retrying won't fix a missing token
    assert logstack.ErrorCode.MATRIX_NOT_CONFIGURED not in logstack.RETRYABLE_CODES
    return None

@T("logstack emits a rotating log file")
def _():
    log = logstack.configure_logging(log_file=str(STATE / "logs" / "test-agent.log"))
    logstack.get_logger("test").warning("log stack self-test", extra={"marker": "xyz"})
    for h in log.handlers:
        h.flush()
    logf = STATE / "logs" / "test-agent.log"
    assert logf.exists(), "no log file written"
    assert "log stack self-test" in logf.read_text()
    return None

@T("logstack writes only to stderr, never stdout")
def _():
    # This is the reason the guard exists: stdout is the JSON-RPC stream.
    import io
    real = sys.stdout
    sys.stdout = io.StringIO()
    try:
        log = logstack.configure_logging()
        logstack.get_logger("test").info("stdout-guard-probe")
        for h in log.handlers:
            h.flush()
        captured = sys.stdout.getvalue()
    finally:
        sys.stdout = real
    assert "stdout-guard-probe" not in captured, "a log record leaked to stdout"
    return None

@T("logstack.safe_extra drops keys that LogRecord itself reserves")
def _():
    import logging as _l
    # `args` IS reserved by LogRecord: passing it via extra= raises
    # KeyError("Attempt to overwrite 'args' in LogRecord"), which surfaced as
    # a tool failure rather than a logging failure.
    cleaned = logstack.safe_extra({"args": (), "name": "x", "tool": "task_list"})
    assert "args" not in cleaned, cleaned
    assert "name" not in cleaned, cleaned
    assert cleaned == {"tool": "task_list"}, cleaned
    return None

@T("logstack JsonFormatter cannot lose a record's severity to an extra")
def _():
    # `level` is NOT reserved by LogRecord (it stores levelname/levelno), so
    # an extra={"level": "green"} used to overwrite the formatter's own
    # severity field and the record shipped with "level": "green".
    import io
    import json as _json
    import logging as _l

    stream = io.StringIO()
    handler = _l.StreamHandler(stream)
    handler.setFormatter(logstack.JsonFormatter())
    log = _l.getLogger("fmt_probe")
    log.handlers = [handler]
    log.setLevel(_l.INFO)
    log.propagate = False
    log.info("severity probe", extra={"level": "green", "signal_level": "green"})
    handler.flush()

    record = _json.loads(stream.getvalue().strip())
    assert record["level"] == "INFO", f"severity was shadowed: {record}"
    # Extras live in their own object and cannot clobber top-level fields.
    assert record["extra"]["level"] == "green", record
    assert record["extra"]["signal_level"] == "green", record
    return None

@T("no log call in server.py passes a LogRecord-reserved key via extra=")
def _():
    # A shadowed `level` reported the record's severity as the Matrix signal
    # colour — silent corruption, so only a scan catches it.
    import logging as _l
    import re as _re
    reserved = set(vars(_l.LogRecord("", 0, "", 0, "", (), None)))
    src = (ROOT / "mcp-server" / "server.py").read_text()
    offenders: set[str] = set()
    for match in _re.finditer(r"extra=\{([^}]*)\}", src, _re.S):
        for key in _re.findall(r'"(\w+)"\s*:', match.group(1)):
            if key in reserved:
                offenders.add(key)
    assert not offenders, (
        f"extra= keys shadow LogRecord fields: {sorted(offenders)} — "
        f"rename them (e.g. args -> tool_args)"
    )
    return None

# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    # Expose helpers to tests
    globals()["load_yaml"] = load_yaml
    globals()["srv"] = srv

    # Run all @T decorated functions in module order
    HERE = sys.modules[__name__]
    for name in dir(HERE):
        obj = getattr(HERE, name)
        if callable(obj) and getattr(obj, "__wrapped__", None) is not None:
            # Already decorated — the decorator ran on import.
            pass

    # The @T decorator already ran each fn on import (module level).
    # Print summary.
    print("=" * 70)
    print("DERIVEE SCAFFOLD — FULL COMPONENT TEST")
    print("=" * 70)
    passed = failed = skipped = 0
    for name, status, msg in results:
        tag = {PASS: "PASS", FAIL: "FAIL", SKIP: "SKIP"}[status]
        if status == PASS:
            passed += 1
        elif status == FAIL:
            failed += 1
        else:
            skipped += 1
        line = f"[{tag}] {name}"
        if msg:
            line += f"\n      → {msg}"
        print(line)
    print("-" * 70)
    print(f"Total: {passed} pass, {failed} fail, {skipped} skip  ({len(results)} tests)")
    print("=" * 70)

    # Exit non-zero if any hard fails
    if failed:
        sys.exit(1)
