#!/usr/bin/env python3
"""Real integration test: use mcp SDK's stdio_client to talk to server.py.
This speaks the actual framed transport the MCPServer expects.
"""

import json
import os
import sys
import traceback
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession
import anyio

ROOT = os.path.dirname(os.path.abspath(__file__))
SERVER = f"{ROOT}/mcp-server/server.py"

async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER],
        cwd=ROOT,
    )
    async with stdio_client(params) as streams:
        read, write = streams
        async with ClientSession(read, write) as session:
            # 1. Initialize
            init = await session.initialize()
            print(f"[1] initialize → {init.server_info}")

            # 2. List tools — ListToolsResult.tools is the actual list
            tools_result = await session.list_tools()
            tools = tools_result.tools
            names = [t.name for t in tools]
            print(f"[2] list_tools → {names}")
            expected = {"task_list","lexicon_lookup","matrix_signal","local_infer","run_shell"}
            if set(names) != expected:
                print(f"    MISMATCH: {set(names)} != {expected}")
                return False

            # 3. Call task_list
            r = await session.call_tool("task_list", {"action": "list"})
            text = "".join(c.text for c in r.content if c.type == "text")
            if not text.strip():
                print(f"[3] EMPTY RESPONSE from task_list: is_error={r.is_error} "
                      f"content={r.content}")
                return False
            try:
                envelope = json.loads(text)
            except json.JSONDecodeError as exc:
                print(f"[3] task_list returned NON-JSON ({exc}). Raw: {text[:500]!r}")
                return False
            assert envelope.get("ok") is True, envelope
            tasks = envelope["tasks"]
            print(f"[3] task_list → {len(tasks)} tasks, request_id={envelope.get('request_id')}")
            if len(tasks) != 4:
                print(f"    expected 4 seed tasks, got {len(tasks)}: {tasks[:2]}")
                return False

            # 4. Call lexicon_lookup
            r = await session.call_tool("lexicon_lookup", {"term": "scout"})
            text = "".join(c.text for c in r.content if c.type == "text")
            print(f"[4] lexicon_lookup → {text[:120]}")

            # 5. Call run_shell
            r = await session.call_tool("run_shell",
                {"command": "echo stdio-ok-4456", "timeout_sec": 10})
            text = "".join(c.text for c in r.content if c.type == "text")
            shell = json.loads(text)
            assert shell["returncode"] == 0, shell
            assert "stdio-ok-4456" in shell["stdout"], shell
            assert shell["cwd"].startswith(str(ROOT)), shell["cwd"]
            print(f"[5] run_shell → rc=0 cwd={shell['cwd']}")

            # 6. Call matrix_signal — must NOT claim delivery it did not make
            r = await session.call_tool("matrix_signal", {"message": "e2e", "level": "green"})
            text = "".join(c.text for c in r.content if c.type == "text")
            mx = json.loads(text)
            assert "sent" in mx, f"matrix_signal did not report delivery status: {mx}"
            if not mx.get("ok"):
                assert mx["sent"] is False, mx
                assert mx["error"]["code"], mx
                print(f"[6] matrix_signal → not sent: {mx['error']['code']}")
            else:
                assert mx["sent"] is False, (
                    f"unconfigured Matrix claimed delivery: {mx}")
                print(f"[6] matrix_signal → ok=True sent=False "
                      f"({mx.get('status') or mx.get('reason')})")

            # 7. Unknown task id must come back as a structured error, not a crash
            r = await session.call_tool("task_list", {"action": "get", "id": "NOPE"})
            text = "".join(c.text for c in r.content if c.type == "text")
            nf = json.loads(text)
            assert nf["ok"] is False, nf
            assert nf["error"]["code"] == "task.not_found", nf
            print(f"[7] task_list unknown id → {nf['error']['code']}")

    print("\n✅ ALL INTEGRATION TESTS PASSED")
    return True

if __name__ == "__main__":
    try:
        ok = anyio.run(main)
    except BaseException as e:
        # Unwrap anyio ExceptionGroups so the real cause is visible instead of
        # a nested "unhandled errors in a TaskGroup" that hides the line number.
        causes = getattr(e, "exceptions", None) or [e]
        root = causes
        while root and getattr(root[0], "exceptions", None):
            root = root[0].exceptions
        print(f"FAILED: {root[0]!r}" if root else f"FAILED: {e!r}")
        traceback.print_exception(type(root[0]), root[0], root[0].__traceback__)
        sys.exit(1)
    # sys.exit must live outside the try: SystemExit is a BaseException and
    # would otherwise be caught and reported as a failure.
    sys.exit(0 if ok else 1)
