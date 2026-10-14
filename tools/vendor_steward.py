#!/usr/bin/env python3
"""Copy the Steward core into vendor/steward/ from a pinned commit.

Usage: STEWARD_REPO=<path> python3 tools/vendor_steward.py <commit>

Copies the `steward/` package, `policy/` and `pwa/*.js` exactly as they are
at <commit> (via `git archive`, so uncommitted work in the Steward checkout
never leaks in), and records the commit in vendor/steward/VENDORED_FROM.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "vendor" / "steward"
KEEP = ("steward/", "policy/", "pwa/")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    commit = sys.argv[1]
    repo = os.environ.get("STEWARD_REPO")
    if not repo:
        print("STEWARD_REPO is not set", file=sys.stderr)
        return 2
    full = subprocess.run(["git", "-C", repo, "rev-parse", commit], check=True, capture_output=True, text=True).stdout.strip()
    blob = subprocess.run(["git", "-C", repo, "archive", "--format=tar", full], check=True, capture_output=True).stdout
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
        for member in tar.getmembers():
            name = member.name
            if not name.startswith(KEEP) or "/test" in name or "__pycache__" in name:
                continue
            if name.startswith("pwa/") and member.isfile() and not name.endswith(".js"):
                continue
            tar.extract(member, DEST, filter="data")
    (DEST / "VENDORED_FROM").write_text(f"{full}\n", encoding="utf-8")
    print(f"vendored steward {full[:7]} into {DEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
