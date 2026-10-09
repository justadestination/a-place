#!/usr/bin/env python3
"""Article Intake & Instantiation Pipeline (Task 3.5).

Serves staff, venues, and public submissions:
  1. Submit draft -> validates payload & evaluates spam/abuse moderation heuristics.
  2. Review workflow -> approve or reject (all rejections carry a plain-language reason).
  3. Instantiation -> writes markdown with YAML frontmatter to vault, invokes build_zine.py,
     and verifies live node in web/data/zine.json with valid graph edges.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
VAULT_DIR = ROOT / "shadenet" / "horizon" / "vault"
DATA_DIR = ROOT / "shadenet" / "data"
DEFAULT_STORE = DATA_DIR / "intake_submissions.json"
WEB = ROOT / "web"
ZINE_JSON = WEB / "data" / "zine.json"

NOTE_TYPES = {"article", "review", "letter", "editorial"}

SPAM_PATTERNS = [
    r"buy\s+cheap",
    r"online\s+casino",
    r"viagra|cialis",
    r"crypto\s+pump|free\s+crypto",
    r"free\s+followers|get\s+rich\s+quick",
    r"telegram\s*[:@]\s*\w+",
    r"whatsapp\s*[:+]\s*\d+",
    r"click\s+here\s+to\s+win",
]


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned or "article"


def check_spam(title: str, body: str) -> tuple[bool, str]:
    """Check text against spam patterns and abuse heuristics."""
    combined = f"{title}\n{body}".lower()
    for pattern in SPAM_PATTERNS:
        if re.search(pattern, combined):
            return True, "Automated moderation check failed: suspicious promotional or spam patterns detected."

    # Check excessive link stuffing
    links = re.findall(r"https?://[^\s]+", body)
    words = body.split()
    if len(words) < 20 and len(links) >= 3:
        return True, "Automated moderation check failed: excessive link density for short submission."

    return False, ""


class IntakeStore:
    def __init__(self, store_path: Path | None = None):
        self.path = store_path or DEFAULT_STORE
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.submissions: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self.submissions = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.submissions = {}

    def _save(self):
        self.path.write_text(json.dumps(self.submissions, indent=2), encoding="utf-8")

    def get(self, sub_id: str) -> dict[str, Any] | None:
        return self.submissions.get(sub_id)

    def all(self) -> list[dict[str, Any]]:
        return list(self.submissions.values())

    def save(self, record: dict[str, Any]):
        self.submissions[record["id"]] = record
        self._save()


def submit_draft(
    title: str,
    body: str,
    article_type: str = "article",
    author: str = "Anonymous Steward",
    venues: list[str] | None = None,
    events: list[str] | None = None,
    tags: list[str] | None = None,
    store: IntakeStore | None = None,
) -> dict[str, Any]:
    """Submit an article draft for intake. Runs spam checks."""
    if not title or not title.strip():
        raise ValueError("Title is required")
    if not body or not body.strip():
        raise ValueError("Body content is required")

    article_type = article_type.lower()
    if article_type not in NOTE_TYPES:
        raise ValueError(f"Invalid article type: {article_type}. Must be one of {NOTE_TYPES}")

    sub_id = f"sub-{uuid.uuid4().hex[:10]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    venues = venues or []
    events = events or []
    tags = tags or []

    is_spam, spam_reason = check_spam(title, body)

    record = {
        "id": sub_id,
        "title": title.strip(),
        "type": article_type,
        "author": author.strip() or "Anonymous Steward",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "venues": venues,
        "events": events,
        "tags": tags,
        "body": body.strip(),
        "status": "rejected" if is_spam else "pending",
        "rejection_reason": spam_reason if is_spam else None,
        "submitted_at": now_iso,
        "reviewed_at": now_iso if is_spam else None,
        "instantiated_file": None,
        "node_id": None,
    }

    st = store or IntakeStore()
    st.save(record)
    return record


def reject_submission(sub_id: str, reason: str, store: IntakeStore | None = None) -> dict[str, Any]:
    """Reject an article submission with a plain-language reason."""
    if not reason or not reason.strip():
        raise ValueError("Rejections must carry a plain-language reason")

    st = store or IntakeStore()
    record = st.get(sub_id)
    if not record:
        raise KeyError(f"Submission {sub_id} not found")

    record["status"] = "rejected"
    record["rejection_reason"] = reason.strip()
    record["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    st.save(record)
    return record


def approve_and_instantiate(
    sub_id: str,
    vault_dir: Path | None = None,
    zine_json: Path | None = None,
    store: IntakeStore | None = None,
) -> dict[str, Any]:
    """Approve a submission, instantiate into markdown vault, and rebuild zine graph."""
    st = store or IntakeStore()
    record = st.get(sub_id)
    if not record:
        raise KeyError(f"Submission {sub_id} not found")

    if record["status"] == "rejected":
        raise ValueError(f"Cannot instantiate a rejected submission: {record.get('rejection_reason')}")

    target_vault = vault_dir or VAULT_DIR
    target_vault.mkdir(parents=True, exist_ok=True)

    slug = slugify(record["title"])
    filename = f"{slug}.md"
    file_path = target_vault / filename

    # Avoid colliding with existing different files
    counter = 1
    while file_path.exists():
        # Check if it belongs to this submission
        existing_text = file_path.read_text(encoding="utf-8")
        if f"title: \"{record['title']}\"" in existing_text:
            break
        counter += 1
        file_path = target_vault / f"{slug}-{counter}.md"

    # YAML frontmatter format
    venues_fmt = "[" + ", ".join(record["venues"]) + "]" if record["venues"] else "[]"
    events_fmt = "[" + ", ".join(record["events"]) + "]" if record["events"] else "[]"
    tags_fmt = "[" + ", ".join(record["tags"]) + "]" if record["tags"] else "[]"

    frontmatter_content = f"""---
title: "{record['title']}"
type: {record['type']}
author: "{record['author']}"
date: {record['date']}
venues: {venues_fmt}
events: {events_fmt}
tags: {tags_fmt}
status: published
---

{record['body']}
"""
    file_path.write_text(frontmatter_content, encoding="utf-8")

    # Run build_zine.py
    build_script = WEB / "tools" / "build_zine.py"
    target_zine_json = zine_json or ZINE_JSON
    res = subprocess.run(
        [sys.executable, str(build_script), "--vault", str(target_vault), "--out", str(target_zine_json)],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(f"build_zine.py failed: {res.stderr}\n{res.stdout}")

    # Inspect zine graph
    graph = json.loads(target_zine_json.read_text(encoding="utf-8"))
    node_id = f"note:{file_path.stem}"
    node = next((n for n in graph.get("nodes", []) if n.get("id") == node_id), None)
    node_edges = [
        e for e in graph.get("edges", [])
        if e.get("source") == node_id or e.get("target") == node_id
    ]

    record["status"] = "instantiated"
    record["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    record["instantiated_file"] = str(file_path)
    record["node_id"] = node_id
    st.save(record)

    return {
        "submission": record,
        "file": str(file_path),
        "node": node,
        "edges": node_edges,
    }


def main():
    parser = argparse.ArgumentParser(description="Article Intake Pipeline")
    subparsers = parser.add_subparsers(dest="command")

    # submit
    sub_p = subparsers.add_parser("submit", help="Submit draft article")
    sub_p.add_argument("--title", required=True, help="Article title")
    sub_p.add_argument("--body", required=True, help="Article markdown body")
    sub_p.add_argument("--type", default="article", choices=list(NOTE_TYPES), help="Article type")
    sub_p.add_argument("--author", default="Anonymous Steward", help="Author name or URI")
    sub_p.add_argument("--venues", nargs="*", default=[], help="Venue IDs")
    sub_p.add_argument("--events", nargs="*", default=[], help="Event IDs")
    sub_p.add_argument("--tags", nargs="*", default=[], help="Tags")

    # reject
    rej_p = subparsers.add_parser("reject", help="Reject a submission with reason")
    rej_p.add_argument("--id", required=True, help="Submission ID")
    rej_p.add_argument("--reason", required=True, help="Plain-language rejection reason")

    # approve
    app_p = subparsers.add_parser("approve", help="Approve and instantiate submission")
    app_p.add_argument("--id", required=True, help="Submission ID")

    # list
    subparsers.add_parser("list", help="List all submissions")

    args = parser.parse_args()
    store = IntakeStore()

    if args.command == "submit":
        rec = submit_draft(
            title=args.title,
            body=args.body,
            article_type=args.type,
            author=args.author,
            venues=args.venues,
            events=args.events,
            tags=args.tags,
            store=store,
        )
        print(f"Draft submitted: {rec['id']} (status: {rec['status']})")
        if rec.get("rejection_reason"):
            print(f"  Reason: {rec['rejection_reason']}")
    elif args.command == "reject":
        rec = reject_submission(args.id, args.reason, store=store)
        print(f"Submission {rec['id']} rejected: {rec['rejection_reason']}")
    elif args.command == "approve":
        result = approve_and_instantiate(args.id, store=store)
        print(f"Submission {args.id} instantiated successfully:")
        print(f"  File: {result['file']}")
        print(f"  Node ID: {result['submission']['node_id']}")
        print(f"  Edges: {len(result['edges'])}")
    elif args.command == "list":
        for rec in store.all():
            print(f"[{rec['status'].upper()}] {rec['id']}: {rec['title']} ({rec['author']})")
            if rec.get("rejection_reason"):
                print(f"  Reason: {rec['rejection_reason']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
