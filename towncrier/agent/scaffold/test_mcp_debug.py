#!/usr/bin/env python3
"""Debug: dump raw JSON-RPC exchange with server.py over stdio."""

import json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVER = ROOT / "mcp-server" / "server.py"

proc = subprocess.Popen(
    [sys.executable, str(SERVER)],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    cwd=ROOT, text=True,
)
time.sleep(0.5)

def send(msg):
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()

def recv(timeout=5):
    deadline = time.monotonic() + timeout
    buf = ""
    while time.monotonic() < deadline:
        chunk = proc.stdout.readline()
        if not chunk:
            print("STDOUT CLOSED")
            return None
        buf += chunk
        print(f"  << {chunk.strip()[:120]}")
        try:
            return json.loads(buf.strip())
        except json.JSONDecodeError:
            pass
    print("TIMEOUT")
    return None

# Build initialize request (MCP 2024 protocol)
req = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": 2024,
        "clientInfo": {"name": "debug-client", "version": "1.0"},
        "capabilities": {"tools": {}},
    },
}
print(">>> sending initialize")
send(req)
resp = recv()
print(f"\nResponse: {resp}")

# Send initialized notification
print("\n>>> sending initialized notification")
send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
time.sleep(0.3)

# tools/list
print("\n>>> sending tools/list")
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
resp2 = recv()
print(f"\nResponse: {resp2}")

proc.stdin.close()
proc.terminate()
proc.wait(timeout=3)
print(f"\nserver exit: {proc.returncode}")
err = proc.stderr.read()
if err.strip():
    print(f"stderr:\n{err[:500]}")
