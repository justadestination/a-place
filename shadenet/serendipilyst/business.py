"""Business nodes and the flags anchored on them.

Decision 002: a venue posts an offer by anchoring a flag on its node, and
the node's inbox is the only contact. The inbox is the node's own relay
address. The Steward that runs the node is stored as ``controller`` and
is never published, so a venue can't be traced to a person's flags.

A node may name a NightCal ``venue_id``. The name is a claim until an
operator verifies it; until then the sheet doesn't show it.
"""

from __future__ import annotations

import json
from typing import Any

from shadenet.serendipilyst import policy
from shadenet.serendipilyst.fields import KEEP, actor as check_actor, as_bool, given, skills, text
from shadenet.serendipilyst.flash import settle_flash
from shadenet.serendipilyst.intents import LINES, settle_profile
from shadenet.serendipilyst.relay import new_alias
from shadenet.serendipilyst.store import FlagError, FlagStore, load_obj, loads, new_id, now_iso

NODE_FIELDS = (
    "name", "venue_id", "anonymous", "listed", "place_id", "appearance", "order",
    "intents", "good_at", "enjoy", "refuse",
)
FLAG_FIELDS = ("title", "body", "skills", "anonymous")


def _node_row(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "kind": "business_node",
        "name": row["name"],
        "inbox": row["inbox"],
        "controller": row["controller"],
        "venue_id": row["venue_id"] or "",
        "venue_verified": bool(row["venue_verified"]),
        "anonymous": bool(row["anonymous"]),
        "listed": bool(row["listed"]),
        "listed_at": row["listed_at"] or "",
        "place_id": row["place_id"] or "",
        "appearance": load_obj(row["appearance"]),
        "intents": loads(row["intents"]),
        "good_at": row["good_at"] or "",
        "enjoy": row["enjoy"] or "",
        "refuse": row["refuse"] or "",
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _flag_row(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "kind": "business",
        "node_id": row["node_id"],
        "node_name": row["node_name"],
        "inbox": row["inbox"],
        "title": row["title"],
        "body": row["body"],
        "skills": loads(row["skills"]),
        "anonymous": bool(row["anonymous"]),
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


_FLAG_SELECT = """
    SELECT f.*, n.name AS node_name, n.inbox AS inbox, n.controller AS controller
      FROM business_flags f
      JOIN business_nodes n ON n.id = f.node_id
"""


def _owned_node(store: FlagStore, node_id: str, controller: str):
    node = store.query_one("SELECT * FROM business_nodes WHERE id = ?", (node_id,))
    if node is None:
        raise FlagError("not_found", f"business node {node_id} does not exist")
    if node["controller"] != controller:
        raise FlagError("scope_denied", "only the node's Steward can change this node")
    return node


def _pick_node(store: FlagStore, controller: str, node_id: str | None):
    """The node a write means. A Steward with several nodes has to name one."""
    if node_id:
        return _owned_node(store, node_id, controller)
    rows = store.query_all("SELECT * FROM business_nodes WHERE controller = ?", (controller,))
    if len(rows) > 1:
        raise FlagError("schema_invalid", "you run more than one node; name the node_id")
    return rows[0] if rows else None


def list_nodes(store: FlagStore, *, active_only: bool = True) -> list[dict[str, Any]]:
    where = "WHERE status = 'active'" if active_only else ""
    rows = store.query_all(f"SELECT * FROM business_nodes {where} ORDER BY updated_at DESC")
    return [_node_row(row) for row in rows]


def upsert_node(
    store: FlagStore,
    *,
    actor: str,
    node_id: str | None = None,
    new: bool = False,
    **changes: Any,
) -> dict[str, Any]:
    """Create a node, or change the fields a write names.

    ``new=True`` opens another node for a Steward that already runs one.
    """
    controller = check_actor(actor)
    unknown = set(changes) - set(NODE_FIELDS)
    if unknown:
        raise FlagError("schema_invalid", f"a business node has no {sorted(unknown)[0]}")
    with store.transaction():
        current = None if new and not node_id else _pick_node(store, controller, node_id)
        cur = _node_row(current) if current is not None else None

        if "name" in changes and given(changes["name"]):
            label = text(changes["name"], "name", 120, required=True)
        elif cur:
            label = cur["name"]
        else:
            raise FlagError("schema_invalid", "name is required")
        venue = text(changes["venue_id"], "venue_id", 80) if given(changes.get("venue_id", KEEP)) else (
            cur["venue_id"] if cur else "")
        verified = bool(cur and cur["venue_verified"] and venue == cur["venue_id"])
        hidden = as_bool(changes["anonymous"], True) if given(changes.get("anonymous", KEEP)) else (
            cur["anonymous"] if cur else True)

        on_map, place, look, heard = settle_flash(
            listed=changes.get("listed", KEEP),
            place_id=changes.get("place_id", KEEP),
            appearance=changes.get("appearance", KEEP),
            order=changes.get("order") or None,
            current_listed=cur["listed"] if cur else False,
            current_place=cur["place_id"] if cur else "",
            current_appearance=cur["appearance"] if cur else None,
        )
        marks, lines = settle_profile(
            heard,
            intents=changes.get("intents", KEEP),
            lines={k: changes.get(k, KEEP) for k in LINES},
            current_intents=cur["intents"] if cur else [],
            current_lines={k: cur[k] for k in LINES} if cur else {},
        )
        stamp = now_iso()
        renewing = on_map and (not cur or not cur["listed"] or "listed" in changes or bool(changes.get("order")))
        listed_at = stamp if renewing else (cur["listed_at"] if cur and on_map else None)
        if on_map and not (cur and cur["listed"] and policy.fresh(cur["listed_at"])):
            policy.admit(store, controller, adding=1)

        values = {
            "name": label, "venue_id": venue or None, "venue_verified": int(verified),
            "anonymous": int(bool(hidden)), "listed": int(on_map), "listed_at": listed_at or None,
            "place_id": place or None, "appearance": look, "intents": json.dumps(marks), **lines,
            "status": "active", "updated_at": stamp,
        }
        if current is None:
            saved_id = new_id("biz")
            inbox = new_alias()
            columns = ["id", "inbox", "controller", "created_at", *values]
            store.execute(
                f"INSERT INTO business_nodes ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                (saved_id, inbox, controller, stamp, *values.values()),
            )
            store.execute(
                "INSERT INTO relays (alias, ref, target, created_at) VALUES (?, ?, ?, ?)",
                (inbox, f"node:{saved_id}", controller, stamp),
            )
        else:
            saved_id = current["id"]
            assignments = ", ".join(f"{column} = ?" for column in values)
            store.execute(f"UPDATE business_nodes SET {assignments} WHERE id = ?", (*values.values(), saved_id))
        return _node_row(store.query_one("SELECT * FROM business_nodes WHERE id = ?", (saved_id,)))


def verify_venue(store: FlagStore, *, node_id: str, verified: bool = True) -> dict[str, Any]:
    """Operator step: the node really is the venue it names."""
    with store.transaction():
        node = store.query_one("SELECT * FROM business_nodes WHERE id = ?", (node_id,))
        if node is None:
            raise FlagError("not_found", f"business node {node_id} does not exist")
        if verified and not node["venue_id"]:
            raise FlagError("schema_invalid", "that node doesn't name a venue")
        store.execute(
            "UPDATE business_nodes SET venue_verified = ?, updated_at = ? WHERE id = ?",
            (int(verified), now_iso(), node_id),
        )
        return _node_row(store.query_one("SELECT * FROM business_nodes WHERE id = ?", (node_id,)))


def pending_venues(store: FlagStore) -> list[dict[str, Any]]:
    rows = store.query_all(
        "SELECT * FROM business_nodes WHERE venue_id IS NOT NULL AND venue_verified = 0 AND status = 'active'"
    )
    return [_node_row(row) for row in rows]


def anchor_flag(
    store: FlagStore,
    *,
    actor: str,
    node_id: str,
    flag_id: str | None = None,
    **changes: Any,
) -> dict[str, Any]:
    """Anchor an offer on a node the actor runs, or change the fields named."""
    controller = check_actor(actor)
    unknown = set(changes) - set(FLAG_FIELDS)
    if unknown:
        raise FlagError("schema_invalid", f"a business flag has no {sorted(unknown)[0]}")
    with store.transaction():
        node = _owned_node(store, node_id, controller)
        if node["status"] != "active":
            raise FlagError("schema_invalid", "business node is not active")
        current = None
        if flag_id:
            current = store.query_one("SELECT * FROM business_flags WHERE id = ?", (flag_id,))
            if current is None:
                raise FlagError("not_found", f"business flag {flag_id} does not exist")
            if current["node_id"] != node_id:
                raise FlagError("scope_denied", "flag is anchored on a different node")

        def pick(key: str, clean, stored: Any) -> Any:
            if key in changes and given(changes[key]):
                return clean(changes[key])
            if current is None and key in ("title", "body"):
                raise FlagError("schema_invalid", f"{key} is required")
            return stored

        heading = pick("title", lambda v: text(v, "title", 160, required=True), current and current["title"])
        said = pick("body", lambda v: text(v, "body", 4000, required=True), current and current["body"])
        tags = pick("skills", skills, loads(current["skills"]) if current else [])
        hidden = pick("anonymous", lambda v: as_bool(v, True), bool(current["anonymous"]) if current else True)
        stamp = now_iso()
        if current is None or current["status"] != "active" or not policy.fresh(current["updated_at"]):
            policy.admit(store, controller, adding=1)
        if current is None:
            saved_id = new_id("flg")
            store.execute(
                """
                INSERT INTO business_flags (
                    id, node_id, title, body, skills, anonymous, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (saved_id, node_id, heading, said, json.dumps(tags), int(bool(hidden)), stamp, stamp),
            )
        else:
            saved_id = current["id"]
            store.execute(
                """
                UPDATE business_flags
                   SET title = ?, body = ?, skills = ?, anonymous = ?, status = 'active', updated_at = ?
                 WHERE id = ?
                """,
                (heading, said, json.dumps(tags), int(bool(hidden)), stamp, saved_id),
            )
        return _flag_row(store.query_one(f"{_FLAG_SELECT} WHERE f.id = ?", (saved_id,)))


def list_flags(store: FlagStore, *, node_id: str | None = None, active_only: bool = True) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[str] = []
    if active_only:
        clauses += ["f.status = 'active'", "n.status = 'active'"]
    if node_id:
        clauses.append("f.node_id = ?")
        params.append(node_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = store.query_all(f"{_FLAG_SELECT} {where} ORDER BY f.updated_at DESC", tuple(params))
    return [_flag_row(row) for row in rows]


def retract_flag(store: FlagStore, *, actor: str, flag_id: str) -> dict[str, Any]:
    controller = check_actor(actor)
    with store.transaction():
        current = store.query_one(f"{_FLAG_SELECT} WHERE f.id = ?", (flag_id,))
        if current is None:
            raise FlagError("not_found", f"business flag {flag_id} does not exist")
        if current["controller"] != controller:
            raise FlagError("scope_denied", "only the node's Steward can retract this flag")
        store.execute(
            "UPDATE business_flags SET status = 'retracted', updated_at = ? WHERE id = ?",
            (now_iso(), flag_id),
        )
        return _flag_row(store.query_one(f"{_FLAG_SELECT} WHERE f.id = ?", (flag_id,)))


def retract_node(store: FlagStore, *, actor: str, node_id: str) -> dict[str, Any]:
    """Retract a node and every flag anchored on it."""
    controller = check_actor(actor)
    with store.transaction():
        _owned_node(store, node_id, controller)
        stamp = now_iso()
        store.execute(
            "UPDATE business_flags SET status = 'retracted', updated_at = ? WHERE node_id = ?",
            (stamp, node_id),
        )
        store.execute(
            "UPDATE business_nodes SET status = 'retracted', updated_at = ? WHERE id = ?",
            (stamp, node_id),
        )
        return _node_row(store.query_one("SELECT * FROM business_nodes WHERE id = ?", (node_id,)))
