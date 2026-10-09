#!/usr/bin/env python3
"""CLI runner and supervisor for ShadeNet Automations (Task 6.9).

Usage:
    python3 tools/automations.py --status
    python3 tools/automations.py --run <automation_name>
    python3 tools/automations.py --run-all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shadenet.automations import default_registry


def format_table(rows: list[dict[str, str]], headers: list[str]) -> str:
    col_widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            col_widths[h] = max(col_widths[h], len(str(row.get(h, ""))))

    line = "+-" + "-+-".join("-" * col_widths[h] for h in headers) + "-+"
    header_str = "| " + " | ".join(h.ljust(col_widths[h]) for h in headers) + " |"

    body_lines = []
    for r in rows:
        row_str = "| " + " | ".join(str(r.get(h, "")).ljust(col_widths[h]) for h in headers) + " |"
        body_lines.append(row_str)

    return "\n".join([line, header_str, line] + body_lines + [line])


def main() -> int:
    parser = argparse.ArgumentParser(description="ShadeNet Automations Runner")
    parser.add_argument("--status", action="store_true", help="Show status of all registered automations")
    parser.add_argument("--json", action="store_true", help="Output status in JSON format")
    parser.add_argument("--run", type=str, metavar="NAME", help="Run a specific automation by name")
    parser.add_argument("--run-all", action="store_true", help="Run all registered automations")

    args = parser.parse_args()

    if args.status or (not args.run and not args.run_all):
        tasks = default_registry.list_tasks()
        if args.json:
            print(json.dumps(tasks, indent=2))
            return 0

        rows = [
            {
                "Automation": t["name"],
                "Owner": t["owner"],
                "Schedule": t["schedule"],
                "Status": t["last_status"].upper(),
                "Failures": str(t["failure_count"]),
                "Last Run": (t["last_run"] or "Never")[:19],
            }
            for t in tasks
        ]
        headers = ["Automation", "Owner", "Schedule", "Status", "Failures", "Last Run"]
        print("\n=== ShadeNet Scheduled Automations ===")
        print(format_table(rows, headers))
        print()
        return 0

    if args.run:
        print(f"Executing automation: {args.run}...")
        try:
            res = default_registry.run_task(args.run)
            if res.get("success"):
                print(f"SUCCESS: {args.run} completed successfully.")
                print(json.dumps(res.get("result", {}), indent=2))
                return 0
            else:
                print(f"FAILURE: {args.run} failed: {res.get('error')}", file=sys.stderr)
                return 1
        except KeyError:
            print(f"Error: Unknown automation '{args.run}'.", file=sys.stderr)
            return 2

    if args.run_all:
        print("Executing all scheduled automations...")
        res = default_registry.run_all()
        for name, task_res in res["results"].items():
            status_icon = "✓" if task_res.get("success") else "✗"
            print(f"  {status_icon} {name.ljust(25)} -> {task_res.get('last_status', 'failed') if not task_res.get('success') else 'OK'}")
            if not task_res.get("success"):
                print(f"    Error: {task_res.get('error')}", file=sys.stderr)

        if res.get("all_passed"):
            print("\nALL AUTOMATIONS PASSED.")
            return 0
        else:
            print("\nONE OR MORE AUTOMATIONS FAILED.", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
