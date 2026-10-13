"""Business node and the flag anchored on it.

Decision 002: a venue posts an offer by anchoring a flag on its node.
The node's inbox is the only contact. The person behind the venue is not
stored. One node per inbox.
"""

from __future__ import annotations

import json
from typing import Any

from shadenet.serendipilyst.flash import settle_flash
from shadenet.serendipilyst.intents import settle_profile
from shadenet.serendipilyst.personal import _actor, _skills, _text
from shadenet.serendipilyst.store import FlagError, FlagStore, load_obj, loads, new_id, now_iso


def _node_row(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "kind": "business_node",
        "name": row["name"],
        "inbox": row["inbox"],
        "venue_id": row["venue_id"] or "",
        "anonymous": bool(row["anonymous"]),
        "listed": bool(row["listed"]),
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


def _owned_node(store: FlagStore, node_id: str, actor: str):
    node = store.query_one("SELECT * FROM business_nodes WHERE id = ?", (node_id,))
    if node is None:
        raise FlagError("not_found", f"business node {node_id} does not exist")
    if node["inbox"] != actor:
        raise FlagError("scope_denied", "only the node inbox can change this node")
    if node["status"] != "active":
        raise FlagError("schema_invalid", "business node is not active")
    return node


def list_nodes(store: FlagStore, *, active_only: bool = True) -> list[dict[str, Any]]:
    if active_only:
        rows = store.query_all(
            "SELECT * FROM business_nodes WHERE status = 'active' ORDER BY updated_at DESC"
        )
    else:
        rows = store.query_all("SELECT * FROM business_nodes ORDER BY updated_at DESC")
    return [_node_row(row) for row in rows]


def upsert_node(
    store: FlagStore,
    *,
    actor: str,
    name: str,
    node_id: str | None = None,
    venue_id: str | None = None,
    anonymous: bool = True,
    listed: bool | None = False,
    place_id: str | None = None,
    appearance: dict | None = None,
    order: str | None = None,
    intents: list | None = None,
    good_at: str | None = None,
    enjoy: str | None = None,
    refuse: str | None = None,
) -> dict[str, Any]:
    """Create or update the business node whose inbox is the actor.

    Each write replaces the node, including its public place and flash.
    An order changes only the parts it names.
    """
    inbox = _actor(actor)
    label = _text(name, "name", 120, required=True)
    venue = _text(venue_id or "", "venue_id", 80)
    stamp = now_iso()

    current = None
    if node_id:
        current = store.query_one("SELECT * FROM business_nodes WHERE id = ?", (node_id,))
        if current is None:
            raise FlagError("not_found", f"business node {node_id} does not exist")
        if current["inbox"] != inbox:
            raise FlagError("scope_denied", "only the node inbox can change this node")
    else:
        current = store.query_one("SELECT * FROM business_nodes WHERE inbox = ?", (inbox,))

    on_map, place, look, heard_profile = settle_flash(
        listed=listed,
        place_id=place_id,
        appearance=appearance,
        order=order,
        current_listed=bool(current["listed"]) if current is not None else False,
        current_place=(current["place_id"] or "") if current is not None else "",
        current_appearance=load_obj(current["appearance"]) if current is not None else None,
    )
    marks, skilled, liked, refused = settle_profile(
        heard_profile,
        ordered=bool((order or "").strip()),
        intents=intents,
        good_at=good_at,
        enjoy=enjoy,
        refuse=refuse,
        current_intents=loads(current["intents"]) if current is not None else [],
        current_good=(current["good_at"] or "") if current is not None else "",
        current_enjoy=(current["enjoy"] or "") if current is not None else "",
        current_refuse=(current["refuse"] or "") if current is not None else "",
    )
    fields = (
        label, venue or None, int(bool(anonymous)),
        int(on_map), place or None, look,
        json.dumps(marks), skilled, liked, refused, stamp,
    )
    if current is not None:
        saved_id = current["id"]
        store.execute(
            """
            UPDATE business_nodes
               SET name = ?, venue_id = ?, anonymous = ?, listed = ?, place_id = ?,
                   appearance = ?, intents = ?, good_at = ?, enjoy = ?, refuse = ?,
                   status = 'active', updated_at = ?
             WHERE id = ?
            """,
            (*fields, saved_id),
        )
    else:
        saved_id = new_id("biz")
        store.execute(
            """
            INSERT INTO business_nodes (
                id, name, inbox, venue_id, anonymous, listed, place_id, appearance,
                intents, good_at, enjoy, refuse,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (saved_id, label, inbox, venue or None, int(bool(anonymous)),
             int(on_map), place or None, look,
             json.dumps(marks), skilled, liked, refused, stamp, stamp),
        )
    row = store.query_one("SELECT * FROM business_nodes WHERE id = ?", (saved_id,))
    return _node_row(row)


def anchor_flag(
    store: FlagStore,
    *,
    actor: str,
    node_id: str,
    title: str,
    body: str,
    flag_id: str | None = None,
    skills: list | None = None,
    anonymous: bool = True,
) -> dict[str, Any]:
    """Anchor or replace an offer on a business node the actor owns."""
    inbox = _actor(actor)
    _owned_node(store, node_id, inbox)
    heading = _text(title, "title", 160, required=True)
    text = _text(body, "body", 4000, required=True)
    tags = _skills(skills)
    stamp = now_iso()

    if flag_id:
        current = store.query_one("SELECT * FROM business_flags WHERE id = ?", (flag_id,))
        if current is None:
            raise FlagError("not_found", f"business flag {flag_id} does not exist")
        if current["node_id"] != node_id:
            raise FlagError("scope_denied", "flag is anchored on a different node")
        store.execute(
            """
            UPDATE business_flags
               SET title = ?, body = ?, skills = ?, anonymous = ?, status = 'active', updated_at = ?
             WHERE id = ?
            """,
            (heading, text, json.dumps(tags), int(bool(anonymous)), stamp, flag_id),
        )
        saved_id = flag_id
    else:
        saved_id = new_id("flg")
        store.execute(
            """
            INSERT INTO business_flags (
                id, node_id, title, body, skills, anonymous, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (saved_id, node_id, heading, text, json.dumps(tags), int(bool(anonymous)), stamp, stamp),
        )
    row = store.query_one(
        """
        SELECT f.*, n.name AS node_name, n.inbox AS inbox
          FROM business_flags f
          JOIN business_nodes n ON n.id = f.node_id
         WHERE f.id = ?
        """,
        (saved_id,),
    )
    return _flag_row(row)


def list_flags(store: FlagStore, *, node_id: str | None = None, active_only: bool = True) -> list[dict[str, Any]]:
    clauses = []
    params: list[str] = []
    if active_only:
        clauses.append("f.status = 'active'")
        clauses.append("n.status = 'active'")
    if node_id:
        clauses.append("f.node_id = ?")
        params.append(node_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = store.query_all(
        f"""
        SELECT f.*, n.name AS node_name, n.inbox AS inbox
          FROM business_flags f
          JOIN business_nodes n ON n.id = f.node_id
          {where}
         ORDER BY f.updated_at DESC
        """,
        tuple(params),
    )
    return [_flag_row(row) for row in rows]


def retract_flag(store: FlagStore, *, actor: str, flag_id: str) -> dict[str, Any]:
    inbox = _actor(actor)
    current = store.query_one(
        """
        SELECT f.*, n.name AS node_name, n.inbox AS inbox
          FROM business_flags f
          JOIN business_nodes n ON n.id = f.node_id
         WHERE f.id = ?
        """,
        (flag_id,),
    )
    if current is None:
        raise FlagError("not_found", f"business flag {flag_id} does not exist")
    if current["inbox"] != inbox:
        raise FlagError("scope_denied", "only the node inbox can retract this flag")
    store.execute(
        "UPDATE business_flags SET status = 'retracted', updated_at = ? WHERE id = ?",
        (now_iso(), flag_id),
    )
    row = store.query_one(
        """
        SELECT f.*, n.name AS node_name, n.inbox AS inbox
          FROM business_flags f
          JOIN business_nodes n ON n.id = f.node_id
         WHERE f.id = ?
        """,
        (flag_id,),
    )
    return _flag_row(row)


def retract_node(store: FlagStore, *, actor: str, node_id: str) -> dict[str, Any]:
    """Retract a business node and every flag anchored on it."""
    inbox = _actor(actor)
    current = store.query_one("SELECT * FROM business_nodes WHERE id = ?", (node_id,))
    if current is None:
        raise FlagError("not_found", f"business node {node_id} does not exist")
    if current["inbox"] != inbox:
        raise FlagError("scope_denied", "only the node inbox can retract this node")
    stamp = now_iso()
    store.execute(
        "UPDATE business_flags SET status = 'retracted', updated_at = ? WHERE node_id = ?",
        (stamp, node_id),
    )
    store.execute(
        "UPDATE business_nodes SET status = 'retracted', updated_at = ? WHERE id = ?",
        (stamp, node_id),
    )
    row = store.query_one("SELECT * FROM business_nodes WHERE id = ?", (node_id,))
    return _node_row(row)
