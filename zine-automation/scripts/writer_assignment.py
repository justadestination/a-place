#!/usr/bin/env python3
"""Gate and pick for one writer run. Prints a stable SKIP, or a unique PROCEED.

Hermes cron uses this as a monitor script. Identical SKIP bytes suppress the
agent. A PROCEED line changes every time, so the writer actually wakes.
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(os.environ.get("ZINE_AUTOMATION_ROOT") or "/var/lib/shadenet/Downloads/shadenet-a/zine-automation")
STATE = ROOT / "scripts" / "state.py"


def main() -> int:
    force = "--force" in sys.argv
    env = os.environ.copy()
    env["ZINE_AUTOMATION_ROOT"] = str(ROOT)
    if not force:
        chance = env.get("ZINE_GATE_CHANCE", "40")
        gate = subprocess.run(
            [sys.executable, str(STATE), "gate", "--chance", chance],
            env=env,
            capture_output=True,
            text=True,
        )
        if gate.returncode == 3:
            print("SKIP")
            return 0
        if gate.returncode != 0:
            sys.stderr.write(gate.stderr or gate.stdout)
            print("ERROR gate failed")
            return 1
    pick = subprocess.run(
        [sys.executable, str(STATE), "pick"],
        env=env,
        capture_output=True,
        text=True,
    )
    if pick.returncode != 0:
        sys.stderr.write(pick.stderr or pick.stdout)
        print("ERROR pick failed")
        return 1
    print("PROCEED")
    print(pick.stdout.strip())
    print(f"assignment={uuid.uuid4()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
