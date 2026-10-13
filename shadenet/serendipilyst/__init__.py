"""Serendipilyst: public flags, the WorldSum sheet, and private accords.

This is not the feature-flag module in ``shadenet/flags.py``.

Records:

- A personal flag pair: one flag for the human, one for their Steward.
  Same owner, linked to each other, each with its own name and content.
- A business node (a venue or host) and the offers anchored on it.

What the public sees (``map_pins`` and ``exposures``) never contains a
Steward address. Contact goes through relay aliases (``relay.py``), so a
posting can't be traced to a profile unless its owner links it, and a venue
can't be traced to the person who runs it.

Dealing (``accord.py``): interest opens a private room, the Steward writes
down the item and price, and both people confirm. A price in XMR can then
become a Monero obligation to the platform (``obligation.py``): oblige,
pay, release. The record builds no payable address and moves no money.
Release is refused until its rule is decided.

Entry points: ``apply_upsert`` and ``apply_deal`` take a command-engine
payload with ``actor`` set by the caller from an authenticated Steward, and
return ``{"ok": ..., "result" | "error": ...}``.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from shadenet.serendipilyst import policy
from shadenet.serendipilyst.accord import confirm_accord, counsel, introduce, rate, read_accord
from shadenet.serendipilyst.obligation import oblige, pay, release
from shadenet.serendipilyst.business import (
    anchor_flag as anchor_business_flag,
    list_flags as list_business_flags,
    list_nodes as list_business_nodes,
    pending_venues,
    retract_flag as retract_business_flag,
    retract_node as retract_business_node,
    upsert_node as upsert_business_node,
    verify_venue,
)
from shadenet.serendipilyst.fields import canon, leaks
from shadenet.serendipilyst.personal import (
    list_flags as list_personal_flags,
    open_flags as open_personal_flags,
    retract_flag as retract_personal_flag,
    upsert_flag as upsert_personal_flag,
)
from shadenet.serendipilyst.relay import offer_ref, relay_for, resolve as resolve_relay
from shadenet.serendipilyst.store import FlagError, FlagStore

__all__ = [
    "FlagError",
    "FlagStore",
    "anchor_business_flag",
    "apply_deal",
    "apply_upsert",
    "configure",
    "confirm_accord",
    "counsel",
    "exposures",
    "get_store",
    "introduce",
    "list_business_flags",
    "list_business_nodes",
    "list_personal_flags",
    "map_pins",
    "oblige",
    "pay",
    "release",
    "open_personal_flags",
    "pending_venues",
    "rate",
    "read_accord",
    "sheet",
    "resolve_relay",
    "retract_business_flag",
    "retract_business_node",
    "retract_personal_flag",
    "upsert_business_node",
    "upsert_personal_flag",
    "use_chat",
    "use_store",
    "verify_venue",
]

_default: FlagStore | None = None
_chat: Any = None


def use_store(store: FlagStore | None) -> None:
    """Install the process store. ``None`` clears it."""
    global _default
    _default = store


def use_chat(chat: Any) -> None:
    """Install the chat connection, or a zero-argument function that opens one.

    A function is called once per deal call and its connection is closed
    after. ``None`` closes the rooms.
    """
    global _chat
    _chat = chat


def configure(db_path: str | Path, chat_opener: Callable[[], Any] | None = None) -> FlagStore:
    """Wire a long-running server: a file-backed store and the chat database."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    store = FlagStore(path)
    use_store(store)
    use_chat(chat_opener)
    return store


@contextmanager
def _chat_session() -> Iterator[Any]:
    # A connection is callable too, so test for one before treating _chat as an opener.
    if _chat is not None and not hasattr(_chat, "execute"):
        conn = _chat()
        try:
            yield conn
        finally:
            conn.close()
    else:
        yield _chat


def get_store() -> FlagStore:
    """The process store. Without ``configure`` it is in memory and lost on exit."""
    global _default
    if _default is None:
        _default = FlagStore(":memory:")
    return _default


def _public_profile(pin: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    """Marks and the three lines are flag content. Ratings and prices are not."""
    if row.get("intents"):
        pin["intents"] = row["intents"]
    for key in ("good_at", "enjoy", "refuse"):
        if row.get(key):
            pin[key] = row[key]
    return pin


def exposures(store: FlagStore | None = None) -> list[dict[str, Any]]:
    """Live offers, for the public sheet.

    Every offer carries a relay inbox. A personal offer gets its own alias,
    and names its flag only when the owner set ``link_postings``.
    """
    db = store or get_store()
    rows: list[dict[str, Any]] = []
    for flag in list_personal_flags(db, active_only=True):
        if not flag["offer_title"] or not policy.fresh(flag["offered_at"]):
            continue
        linked = flag["link_postings"]
        rows.append({
            "kind": "personal",
            "holder": flag["holder"],
            "flag_id": flag["id"] if linked else None,
            "title": flag["offer_title"],
            "body": flag["offer_body"],
            "skills": flag["skills"],
            "anonymous": flag["anonymous"] or not linked,
            "inbox": relay_for(
                db,
                ref=offer_ref(flag["id"], flag["offer_title"], flag["offer_body"]),
                target=flag["owner"],
            ),
        })
    for flag in list_business_flags(db, active_only=True):
        if not policy.fresh(flag["updated_at"]):
            continue
        rows.append({
            "kind": "business",
            "flag_id": flag["id"],
            "node_id": flag["node_id"],
            "title": flag["title"],
            "body": flag["body"],
            "skills": flag["skills"],
            "anonymous": flag["anonymous"],
            "inbox": flag["inbox"],
            "node_name": flag["node_name"],
        })
    return rows


def map_pins(store: FlagStore | None = None) -> list[dict[str, Any]]:
    """Listed places, for the public sheet. An unlisted flag is left out, place and all."""
    db = store or get_store()
    pins: list[dict[str, Any]] = []
    for flag in list_personal_flags(db, active_only=True):
        if not flag["listed"] or not policy.fresh(flag["listed_at"]):
            continue
        pin = {
            "id": flag["id"],
            "kind": "personal",
            "holder": flag["holder"],
            "name": flag["display_name"],
            "place_id": flag["place_id"],
            "appearance": flag["appearance"],
        }
        if flag["address"]:
            pin["address"] = flag["address"]
        pins.append(_public_profile(pin, flag))
    for node in list_business_nodes(db, active_only=True):
        if not node["listed"] or not policy.fresh(node["listed_at"]):
            continue
        pin = {
            "id": node["id"],
            "kind": "business_node",
            "name": node["name"],
            "place_id": node["place_id"],
            "appearance": node["appearance"],
            "inbox": node["inbox"],
        }
        if node["venue_verified"]:
            pin["venue_id"] = node["venue_id"]
        pins.append(_public_profile(pin, node))
    return pins


_PERSONAL = (
    "display_name", "bio", "declarations", "pgp", "availability", "skills",
    "offer_title", "offer_body", "link_postings", "anonymous",
    "listed", "place_id", "appearance", "order", "intents", "good_at", "enjoy", "refuse",
)
_NODE = ("name", "venue_id", "anonymous", "listed", "place_id", "appearance", "order",
         "intents", "good_at", "enjoy", "refuse")
_BUSINESS_FLAG = ("title", "body", "skills", "anonymous")


def _only(payload: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    """The fields a write named. A missing field is kept, so it is not passed."""
    return {name: payload[name] for name in names if name in payload}


def _refused(message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": "schema_invalid", "message": message}}


def apply_upsert(args: dict[str, Any], store: FlagStore | None = None) -> dict[str, Any]:
    """Dispatch one ``flags.upsert`` payload: write or retract a flag or node."""
    found = leaks({k: v for k, v in args.items() if k != "actor"})
    if found:
        return _refused(f"flags carry no {found}; contact goes through the inbox")
    db = store or get_store()
    payload = canon(args)
    kind = payload.get("kind")
    actor = str(payload.get("actor") or "")
    retract = payload.get("retract") is True
    try:
        if kind == "personal":
            if retract:
                result = retract_personal_flag(db, actor=actor, flag_id=str(payload.get("flag_id") or ""))
            elif isinstance(payload.get("human"), dict) and isinstance(payload.get("steward"), dict):
                result = open_personal_flags(
                    db, actor=actor,
                    human=canon(payload["human"]), steward=canon(payload["steward"]),
                )
            elif payload.get("holder"):
                result = upsert_personal_flag(
                    db,
                    actor=actor,
                    holder=str(payload["holder"]),
                    flag_id=payload.get("flag_id"),
                    counterpart_name=payload.get("counterpart_name"),
                    **_only(payload, _PERSONAL),
                )
            else:
                raise FlagError("schema_invalid", "a personal flag opens a human flag and a steward flag")
        elif kind == "business_node":
            node_id = payload.get("node_id") or payload.get("flag_id")
            if retract:
                result = retract_business_node(db, actor=actor, node_id=str(node_id or ""))
            else:
                result = upsert_business_node(
                    db, actor=actor, node_id=node_id, new=payload.get("new") is True,
                    **_only(payload, _NODE),
                )
            result = {k: v for k, v in result.items() if k != "controller"}
        elif kind == "business_flag":
            if retract:
                result = retract_business_flag(db, actor=actor, flag_id=str(payload.get("flag_id") or ""))
            else:
                result = anchor_business_flag(
                    db, actor=actor,
                    node_id=str(payload.get("node_id") or ""),
                    flag_id=payload.get("flag_id"),
                    **_only(payload, _BUSINESS_FLAG),
                )
        else:
            return _refused("kind must be personal, business_node, or business_flag")
    except FlagError as exc:
        return {"ok": False, "error": {"code": exc.code, "message": str(exc)}}
    return {"ok": True, "result": result}


def apply_deal(args: dict[str, Any], store: FlagStore | None = None) -> dict[str, Any]:
    """Dispatch one ``flags.deal`` payload: interest, accord, oblige, pay, release, rate, or counsel."""
    payload = canon(args)
    found = leaks({k: v for k, v in payload.items() if k not in ("actor", "terms", "obligation_id")})
    if found:
        return _refused(f"deals carry no {found}; settle it between you")
    db = store or get_store()
    action = str(payload.get("action") or "")
    actor = str(payload.get("actor") or "")
    where = {
        "room_id": str(payload.get("room_id") or ""),
        "flag_id": str(payload.get("flag_id") or ""),
    }
    try:
        if action == "interest":
            with _chat_session() as chat:
                result = introduce(
                    db, actor=actor, flag_id=where["flag_id"],
                    relay=str(payload.get("relay") or ""),
                    sentence=str(payload.get("sentence") or ""), chat=chat,
                )
        elif action == "accord":
            step = str(payload.get("step") or "read")
            if step == "read":
                if any(payload.get(key) not in (None, "") for key in ("give", "get", "amount", "item")):
                    raise FlagError("schema_invalid", "I read the room. Don't hand me the price.")
                with _chat_session() as chat:
                    result = read_accord(db, actor=actor, chat=chat, **where)
            elif step == "confirm":
                result = confirm_accord(db, actor=actor, terms=str(payload.get("terms") or ""), **where)
            else:
                raise FlagError("schema_invalid", "step must be read or confirm")
        elif action == "oblige":
            result = oblige(db, actor=actor, terms=str(payload.get("terms") or ""), **where)
        elif action in ("pay", "release"):
            step = pay if action == "pay" else release
            result = step(
                db, actor=actor, obligation_id=str(payload.get("obligation_id") or ""),
                tip=payload.get("tip"),
            )
        elif action == "rate":
            result = rate(
                db, actor=actor, personal=payload.get("personal"),
                product=payload.get("product"), word=payload.get("word"), **where,
            )
        elif action == "counsel":
            result = counsel(db, actor=actor)
        else:
            raise FlagError(
                "schema_invalid",
                "action must be interest, accord, oblige, pay, release, rate, or counsel",
            )
    except FlagError as exc:
        return {"ok": False, "error": {"code": exc.code, "message": str(exc)}}
    return {"ok": True, "result": result}


def sheet(store: FlagStore | None = None) -> dict[str, Any]:
    """Everything the public WorldSum sheet shows."""
    return {"pins": map_pins(store), "offers": exposures(store)}
