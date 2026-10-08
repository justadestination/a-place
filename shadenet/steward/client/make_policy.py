#!/usr/bin/env python3
"""Regenerate the steward policy shim from the walkthrough.

    python3 walkthrough.py --demo --out policy.generated.json
    python3 steward/make_policy.py

Wraps the JSON as `window.__POLICY__` so index.html loads from file:// with no
server and no fetch. Run the walkthrough first -- this does not generate the
policy, it only wraps it.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "policy.generated.json"
DST = HERE / "policy.generated.js"

if not SRC.exists():
    raise SystemExit(f"missing {SRC} -- run walkthrough.py --demo first")

policy = json.loads(SRC.read_text())
DST.write_text(
    "// Generated from ../policy.generated.json by make_policy.py.\n"
    "// Edit the JSON, re-run walkthrough.py --demo, then re-run this.\n"
    "window.__POLICY__ = " + json.dumps(policy, indent=2) + ";\n"
)

p = policy.get("presentation", {})
print(f"wrote {DST} ({DST.stat().st_size} bytes)")
print("  zoom     ", p.get("zoom"))
print("  contrast ", p.get("contrast"))
print("  motion   ", p.get("motion"))
print("  density  ", p.get("density"))
