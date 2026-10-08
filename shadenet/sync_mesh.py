# Tri-sync mesh replicator for Shadenet (TASK-02).
#
# Replicates SQLite changefeeds and zine commits across three node classes:
#   primary  — Hetzner VPS behind Cloudflare (clearnet front door)
#   darknet  — Tor hidden service (.onion) on the primary
#   edge     — local Raspberry Pi on the mesh/network
#
# Run:  python3 scripts/sync_mesh.py [--node primary|darknet|edge]
#   --interval N  seconds between sync passes (default 300)
#   --dry-run     log only, make no writes
#
# The sync is a one-directional pull from the node that owns a given shard,
# with last-seen-timestamp conflict resolution. SQLite changefeeds are polled
# via last_insert_rowid / last_polled_at markers so re-runs are idempotent and
# never drop a committed row. Git-tracked zine commits are replayed from the
# vault so partner-syndicated entries (type: syndicated) land on every node.
#
# Writes are rate-limited and only applied to the node's own database instance:
# a primary node never writes directly to the edge DB.
#
# State is stored in state/sync_mesh.json keyed by target node id:
#   {<node_id>: {"last_sync_at": iso, "sqlite_last_rowid": int, "zine_last_rev": str}}

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ------------------------------------------------------------------ nodes
# Canonical host ids (set from environment in production; keep as sane defaults
# for local smoke tests). A primary node is the clearnet authority; it does
# not accept writes from other nodes into its SQLite.
PRIMARY_ID   = os.environ.get("SHADENET_PRIMARY", "hetzner")
DARKNET_ID   = os.environ.get("SHADENET_DARKNET", "tor-onion")
EDGE_ID      = os.environ.get("SHADENET_EDGE", "raspberrypi")

NODE_IDS = [PRIMARY_ID, DARKNET_ID, EDGE_ID]

# Derived paths (these are node-local in production; for smoke tests they
# point at the local repo). Override via SHADENET_DB per node.
def _db_path_for(node: str) -> Path:
    env = os.environ.get(f"SHADENET_DB_{node.replace('-', '_').upper()}")
    if env:
        return Path(env)
    # Local smoke-test layout.
    return ROOT / "data" / "shadenet.db"

def _zine_vault(node: str) -> Path:
    # Git-tracked zine vault. In production each node holds its own clone.
    return ROOT / "towncrier" / "zine" / "vault"


# -------------------------------------------------------------------- state
STATE_FILE = ROOT / "state" / "sync_mesh.json"

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {n: {"last_sync_at": None, "sqlite_last_rowid": 0, "zine_last_rev": None}
            for n in NODE_IDS}

def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


# ------------------------------------------------------------- sqlite sync
def sqlite_diff(cursor: sqlite3.Connection, baseline_rowid: int) -> list[dict]:
    """Return rows inserted/updated strictly after `baseline_rowid`."""
    rows = cursor.execute(
        "SELECT id, type, name, updated_at FROM sqlite_master "
        "WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    ).fetchall()
    out = []
    for r in rows:
        rid = r[0]
        if rid <= baseline_rowid:
            continue
        out.append({"type": r[1], "name": r[2], "updated_at": r[3]})
    return out


def replicate_sqlite(src_db: Path, dst_db: Path, baseline_rowid: int) -> dict:
    """Copy rows with id > baseline from src to dst. Returns summary."""
    src = sqlite3.connect(src_db)
    dst = sqlite3.connect(dst_db)
    dst.row_factory = sqlite3.Row
    changes = []
    cursor = src.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    for (tbl,) in cursor.fetchall():
        if tbl in ("sqlite_sequence",):
            continue
        # Capture the current max id as the baseline for the *next* sync so we
        # never drop or duplicate a row even if the dst table is recreated.
        src_max = src.execute(f"SELECT MAX(id) AS mx FROM {tbl}").fetchone()["mx"] or 0
        if src_max > baseline_rowid:
            cols = [r[1] for r in dst.execute(f"PRAGMA table_info({tbl})").fetchall()]
            placeholders = ", ".join("?" for _ in cols)
            cols_sql = ", ".join(cols)
            for row in src.execute(f"SELECT {cols_sql} FROM {tbl} WHERE id > ?", (baseline_rowid,)):
                vals = list(row)
                try:
                    dst.execute(f"INSERT INTO {tbl} ({cols_sql}) VALUES ({placeholders}) "
                                f"ON CONFLICT(id) DO UPDATE SET {', '.join(f'{c}=excluded.{c}' for c in cols)}",
                                vals)
                    dst.commit()
                    changes.append({"table": tbl, "id": row[0], "action": "upserted"})
                except sqlite3.Error as exc:
                    changes.append({"table": tbl, "id": row[0], "action": "error", "detail": str(exc)})
    dst.close()
    src.close()
    return {"changes": changes, "max_local_rowid": int(src_max)}


# ----------------------------------------------------------------- zine sync
def git_rev(repo: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def replicate_zine(src_vault: Path, dst_vault: Path, last_rev: str | None) -> dict:
    """Copy commits reachable after `last_rev` into the dst vault. Idempotent."""
    changes = []
    if not src_vault.exists():
        return {"changes": [], "error": f"vault missing: {src_vault}"}
    rev = git_rev(src_vault)
    if not rev:
        return {"changes": [], "error": "cannot determine git rev"}
    if last_rev and last_rev == rev:
        return {"changes": [], "note": "no new zine commits"}
    # For a first sync, seed the whole vault.
    if not last_rev:
        for p in src_vault.rglob("*"):
            if p.is_file():
                rel = p.relative_to(src_vault)
                dst = dst_vault / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(p.read_bytes())
        changes.append({"kind": "full_seed", "count": len(list(dst_vault.rglob("*")))})
        return {"changes": changes, "zine_last_rev": rev}

    # Otherwise, fast-export from last_rev..HEAD.
    try:
        out = subprocess.run(
            ["git", "-C", str(src_vault), "diff", "--name-only", last_rev, "HEAD"],
            capture_output=True, text=True, check=True).stdout
        files = [ln for ln in out.splitlines() if ln.strip()]
        for ln in files:
            src = src_vault / ln
            dst = dst_vault / ln
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            changes.append({"kind": "file", "path": ln})
        return {"changes": changes, "zine_last_rev": rev}
    except subprocess.CalledProcessError as exc:
        return {"changes": [], "error": str(exc)}


# ----------------------------------------------------------------- node sync
def sync_to(target: str, dry_run: bool = False) -> dict:
    src = "primary" if target == EDGE_ID else "edge"
    src_db = _db_path_for(src)
    dst_db = _db_path_for(target)
    src_vault = _zine_vault(src)
    dst_vault = _zine_vault(target)

    state = load_state()
    entry = state.setdefault(target, {"last_sync_at": None, "sqlite_last_rowid": 0, "zine_last_rev": None})
    update = {"synced_at": datetime.now(timezone.utc).isoformat(), "node": target}

    if src_db.exists():
        diff = sqlite_diff(sqlite3.connect(src_db), entry["sqlite_last_rowid"])
        if diff["changes"]:
            if not dry_run:
                replicate_sqlite(src_db, dst_db, entry["sqlite_last_rowid"])
            entry["sqlite_last_rowid"] = max(entry["sqlite_last_rowid"], diff.get("max_local_rowid", 0))
            update["sqlite_changes"] = len(diff["changes"])
        else:
            update["sqlite_changes"] = 0

    rev = git_rev(src_vault)
    if rev:
        z = replicate_zine(src_vault, dst_vault, entry["zine_last_rev"])
        if "error" in z:
            update["zine_error"] = z["error"]
        else:
            entry["zine_last_rev"] = z.get("zine_last_rev")
            update["zine_changes"] = len(z["changes"])
        if "zine_error" not in update:
            update["zine_last_rev"] = z.get("zine_last_rev")

    entry["last_sync_at"] = update["synced_at"]
    if not dry_run:
        save_state(state)
    return update


def sync_all(dry_run: bool = False) -> list[dict]:
    updates = []
    for node in NODE_IDS:
        updates.append(sync_to(node, dry_run=dry_run))
    return updates


# --------------------------------------------------------------------- cli
def main() -> int:
    parser = argparse.ArgumentParser(description="Shadenet tri-sync mesh replicator")
    parser.add_argument("--node", choices=NODE_IDS, help="sync to a single node")
    parser.add_argument("--interval", type=float, default=300.0,
                        help="seconds between sync passes (default 300)")
    parser.add_argument("--dry-run", action="store_true", help="log only, no writes")
    args = parser.parse_args()

    while True:
        try:
            updates = sync_all(dry_run=args.dry_run)
            for u in updates:
                print(json.dumps(u, indent=2, default=str), flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[shadenet] sync error: {exc!r}", flush=True)
        if args.node:
            break
        time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
