#!/usr/bin/env python3
"""Quick structured inventory of a small scaffold directory.
Usage: python inventory.py [path]
Prints a JSON-ish summary useful for the scaffold-reviewer skill.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()

def walk():
    files = []
    for p in sorted(ROOT.rglob("*")):
        if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts:
            rel = str(p.relative_to(ROOT))
            size = p.stat().st_size
            files.append({"path": rel, "size": size})
    return files

def detect_signals(files):
    names = {f["path"] for f in files}
    signals = []
    if any("mcp" in n.lower() for n in names):
        signals.append("mcp")
    if any(n.endswith((".yaml", ".yml")) for n in names):
        signals.append("yaml-config")
    if any("matrix" in n.lower() for n in names):
        signals.append("matrix")
    if any("lexicon" in n.lower() for n in names):
        signals.append("lexicon")
    if any("tasks" in n.lower() for n in names):
        signals.append("task-list")
    if any(n.endswith("requirements.txt") or "pyproject.toml" in n for n in names):
        signals.append("python")
    if any("ollama" in n.lower() or "hermes" in n.lower() for n in names):
        signals.append("local-inference")
    return signals

def main():
    files = walk()
    print(json.dumps({
        "root": str(ROOT),
        "file_count": len(files),
        "files": files,
        "signals": detect_signals(files),
    }, indent=2))

if __name__ == "__main__":
    main()
