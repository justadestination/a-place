#!/usr/bin/env python3
"""List the editor queue. QUEUE_EMPTY is stable so an idle zine does not wake the editor.

A non-empty queue includes the current hour, so each scheduled tick retries
until the drafts are published or escalated.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("ZINE_AUTOMATION_ROOT") or "/var/lib/shadenet/Downloads/shadenet-a/zine-automation")


def draft_files() -> list[Path]:
    drafts = ROOT / "drafts"
    if not drafts.is_dir():
        return []
    files = []
    for path in sorted(drafts.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        head = text.split("---", 2)[1] if text.startswith("---") and text.count("---") >= 2 else text
        if "status: draft" in head:
            files.append(path)
    return files


def main() -> int:
    files = draft_files()
    if not files:
        print("QUEUE_EMPTY")
        return 0
    print("DRAFTS")
    print(datetime.now().strftime("%Y-%m-%dT%H"))
    for path in files:
        print(f"drafts/{path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
