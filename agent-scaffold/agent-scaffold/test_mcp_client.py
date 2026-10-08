#!/usr/bin/env python3
"""Real MCP client test — speaks the protocol over stdio to server.py.
Tests initialize + tool_list + tool_call (task_list) end-to-end.
"""

from __future__ import annotations

import json
import select
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SERVER = ROOT / "mcp-server" / "server.py"

# Negotiate against whatever the installed SDK supports rather than a hardcoded
# year — pinning one is how this test ended up speaking a dead protocol.
try:
    from mcp.types.version import LATEST_PROTOCOL_VERSION as PROTOCOL_VERSION
except Exception:  # pragma: no cover - older/newer SDK layout
    PROTOCOL_VERSION = "2025-06-18"

# ---------------------------------------------------------------------------
# Minimal MCP v1 protocol (JSON-RPC 2.0 over stdio)
# ---------------------------------------------------------------------------

class MCPOverSTDIO:
    def __init__(self, proc: subprocess.Popen):
        self.proc = proc
        self._next_id = 0
        self._started = False

    def _send(self, msg: dict) -> None:
        line = json.dumps(msg) + "\n"
        self.proc.stdin.write(line)
        self.proc.stdin.flush()

    def _recv(self, timeout: float = 8.0) -> dict:
        deadline = time.monotonic() + timeout
        buf = ""
        while time.monotonic() < deadline:
            ready, _, _ = select.select([self.proc.stdout], [], [], 0.2)
            if not ready:
                continue
            chunk = self.proc.stdout.readline()
            if not chunk:
                raise EOFError("server closed stdout")
            buf += chunk
            # MCP messages are newline-delimited JSON
            if buf.strip().endswith("}"):
                try:
                    return json.loads(buf.strip())
                except json.JSONDecodeError:
                    pass  #incomplete, keep reading
        raise TimeoutError(f"no complete JSON-RPC message within {timeout}s")

    def initialize(self, server_name: str = "agent-tools") -> dict:
        self._send({
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": "initialize",
            "params": {
                # Must be a version the installed SDK still accepts. It was
                # pinned at 2024, which the server now rejects with
                # -32602 Invalid request parameters.
                "protocolVersion": PROTOCOL_VERSION,
                "clientInfo": {"name": "test-client", "version": "1.0"},
                "capabilities": {},
            },
        })
        self._next_id += 1
        resp = self._recv()
        if "error" in resp:
            raise RuntimeError(f"initialize rejected: {resp['error']}")
        assert resp.get("result") is not None, resp
        # Send initialized notification
        self._send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
        self._started = True
        return resp

    def list_tools(self) -> list[dict]:
        self._send({
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": "tools/list",
            "params": {},
        })
        self._next_id += 1
        resp = self._recv()
        assert resp.get("result", {}).get("tools") is not None
        return resp["result"]["tools"]

    def call_tool(self, name: str, arguments: dict) -> Any:
        self._send({
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        self._next_id += 1
        resp = self._recv()
        result = resp.get("result", {})
        if result.get("isError"):
            raises = result.get("content", [])
            text = "".join(c.get("text", "") for c in raises if c.get("type") == "text")
            raise RuntimeError(f"tool {name} error: {text}")
        return result

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Starting MCP server: {SERVER}")
    proc = subprocess.Popen(
        [sys.executable, str(SERVER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=ROOT,
        text=True,
    )

    # Drain stderr on a background thread. A bare proc.stderr.read() blocks
    # until EOF, which never arrives while the server is alive — that hung
    # this test at step 1.
    stderr_chunks: list[str] = []

    def _drain_stderr() -> None:
        try:
            for line in iter(proc.stderr.readline, ""):
                stderr_chunks.append(line)
        except Exception:
            pass

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    try:
        client = MCPOverSTDIO(proc)

        # 1. Initialize
        print("[1] initialize ...", end=" ", flush=True)
        ir = client.initialize()
        negotiated = ir.get("result", {}).get("protocolVersion", "?")
        print(f"OK (negotiated protocol {negotiated})")

        # 2. List tools
        print("[2] tools/list ...", end=" ", flush=True)
        tools = client.list_tools()
        tool_names = [t["name"] for t in tools]
        print(f"OK → {tool_names}")
        expected = ["task_list", "lexicon_lookup", "matrix_signal", "local_infer", "run_shell"]
        if tool_names != expected:
            print(f"    MISMATCH: expected {expected}")
            sys.exit(1)

        # 3. Call task_list
        print("[3] tools/call task_list ...", end=" ", flush=True)
        result = client.call_tool("task_list", {"action": "list"})
        content = result.get("content", [])
        text_blocks = [c["text"] for c in content if c.get("type") == "text"]
        combined = "".join(text_blocks)
        envelope = json.loads(combined) if combined.strip() else {}
        assert envelope.get("ok") is True, envelope
        tasks = envelope["tasks"]
        print(f"OK → {len(tasks)} tasks")
        if len(tasks) != 4:
            print(f"    expected 4 seed tasks, got {len(tasks)}")
            sys.exit(1)
        ids = [t["id"] for t in tasks]
        print(f"    ids: {ids}")

        # 4. Call lexicon_lookup
        print("[4] tools/call lexicon_lookup ...", end=" ", flush=True)
        result = client.call_tool("lexicon_lookup", {"term": "scout"})
        content = result.get("content", [])
        text = "".join(c["text"] for c in content if c.get("type") == "text")
        parsed = json.loads(text) if text.strip() else {}
        print(f"OK → {parsed}")
        assert parsed.get("meaning") == "research / gather information without acting"

        # 5. Call run_shell
        print("[5] tools/call run_shell ...", end=" ", flush=True)
        result = client.call_tool("run_shell", {"command": "echo mcp-e2e-ok-9876", "timeout_sec": 10})
        content = result.get("content", [])
        text = "".join(c["text"] for c in content if c.get("type") == "text")
        parsed = json.loads(text) if text.strip() else {}
        print(f"OK → rc={parsed.get('returncode')} stdout={parsed.get('stdout','').strip()!r}")
        assert parsed.get("returncode") == 0
        assert "mcp-e2e-ok-9876" in parsed.get("stdout", "")
        assert parsed.get("cwd", "").startswith(str(ROOT.resolve()))

        # 6. Call matrix_signal — must not claim delivery it did not make
        print("[6] tools/call matrix_signal ...", end=" ", flush=True)
        result = client.call_tool("matrix_signal", {"message": "e2e-test", "level": "green"})
        content = result.get("content", [])
        text = "".join(c["text"] for c in content if c.get("type") == "text")
        parsed = json.loads(text) if text.strip() else {}
        assert "sent" in parsed, f"no delivery status reported: {parsed}"
        assert parsed["sent"] is False, f"claimed delivery while unconfigured: {parsed}"
        if parsed.get("ok"):
            print(f"OK → sent=False (unconfigured)")
            assert parsed.get("reason") or parsed.get("status"), parsed
        else:
            print(f"OK → sent=False error={parsed['error']['code']}")

        print()
        print("=" * 60)
        print("ALL 6 MCP PROTOCOL TESTS PASSED")
        print("=" * 60)

    except Exception as e:
        print(f"\nFAILED: {e!r}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        stderr_thread.join(timeout=2)
        if stderr_chunks and "".join(stderr_chunks).strip():
            print(f"\nserver stderr tail:\n{''.join(stderr_chunks)[-800:]}")
