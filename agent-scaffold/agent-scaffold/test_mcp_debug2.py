#!/usr/bin/env python3
"""Debug: probe MCPServer's expected request shape."""

import json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVER = ROOT / "mcp-server" / "server.py"

def run_with(req, label):
    proc = subprocess.Popen(
        [sys.executable, str(SERVER)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=ROOT, text=True,
    )
    time.sleep(0.3)
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    resp = proc.stdout.readline()
    proc.stdin.close()
    proc.terminate()
    proc.wait(timeout=3)
    print(f"\n=== {label} ===")
    print(f">>> {json.dumps(req)[:120]}")
    print(f"<<< {resp.strip()[:200]}")
    err = proc.stderr.read()
    if err.strip():
        print(f"stderr: {err.strip()[:200]}")

# 1. Minimal initialize with full capabilities
run_with({
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": 2024,
        "clientInfo": {"name": "dbg", "version": "1.0"},
        "capabilities": {
            "tools": {},
            "resources": {"subscribe": False, "list": False},
            "prompts": {"list": False},
        },
    },
}, "initialize v1 (full caps)")

# 2. initialize without capabilities
run_with({
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": 2024,
        "clientInfo": {"name": "dbg", "version": "1.0"},
    },
}, "initialize v2 (no caps)")

# 3. tools/list after init+initialized (two msgs in sequence)
proc = subprocess.Popen(
    [sys.executable, str(SERVER)],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    cwd=ROOT, text=True,
)
time.sleep(0.3)
proc.stdin.write(json.dumps({
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": 2024,
        "clientInfo": {"name": "dbg", "version": "1.0"},
        "capabilities": {"tools": {}},
    },
}) + "\n")
proc.stdin.flush()
r1 = proc.stdout.readline().strip()
print(f"init resp: {r1[:150]}")
proc.stdin.write(json.dumps({"jsonrpc":"2.0","method":"initialized","params":{}}) + "\n")
proc.stdin.flush()
time.sleep(0.1)
proc.stdin.write(json.dumps({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}) + "\n")
proc.stdin.flush()
r2 = proc.stdout.readline().strip()
print(f"list resp: {r2[:200]}")
proc.stdin.close()
proc.terminate()
proc.wait(timeout=3)
err = proc.stderr.read()
if err.strip():
    print(f"stderr: {err.strip()[:200]}")
