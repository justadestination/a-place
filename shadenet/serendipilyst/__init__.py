"""Serendipilyst — personal flags and the business flag/node.

Scoped out of the package consolidation and left as names only:

- ``SHADENET_PLAN.md`` and ``TODO.md`` TASK-01 list ``shadenet.serendipilyst``.
  The completed consolidation line and ``SPEC_SHEET.md`` §3.1 shipped
  nightcal, horizon, towncrier, and steward, and stopped there.
- ``SHADENET_PACKAGE_SPEC.md`` draws Serendipilyst in the ecosystem diagram
  and leaves it out of the package manifest.
- ``SHADENET_SPEC.md`` §1 defines Flags. The same section also calls a flag
  an agent card; the record in this package is a flag. §3.A is the personal
  Flag. ``TODO.md`` TASK-11 (public Flag builder) is still open.
- Decision 002 (``docs/decisions/002-market-slot-spec.md``) is the contract:
  a person or a venue anchors an offer on their own node, Serendipilyst only
  collects those flags, settlement stays off the platform, and contact goes
  through the node inbox.
- ``SPEC_SHEET.md`` §5.2 names the ``flags.upsert`` command. The steward
  command registry did not contain it.

This package is that missing slice. It is not the feature-flag module in
``shadenet/flags.py``.

Two records:

- A personal flag is a pair of flags. The human has one and the Steward
  has one. They share the Steward address and point at each other. Each
  flag keeps its own pseudonym, bio, skills, availability, and optional offer.
- A business node is the venue or host. A business flag is an offer anchored
  on that node.

No price, escrow, or legal-identity fields. Anonymous unless the owner says
otherwise.

A listed flag publishes one WorldSum place. An unlisted flag can remember a
place, and that place stays off the map. The flash is American Traditional.
An order can name one part, or the flag can set field, charge, motto, line,
ribbon, and fly. A private room is a chat record, not a homeserver.

An intent is a mark with one sentence. A sale can record the purchaser's
obligation to pay the platform in Monero, and a later release to the seller.
That record is not a price on the flag, and it does not build a payable address.
"""

from __future__ import annotations

from typing import Any

from shadenet.serendipilyst.flash import omitted_listing
from shadenet.serendipilyst.intents import (
    confirm_accord,
    counsel,
    introduce,
    oblige,
    pay,
    read_accord,
    release,
)
from shadenet.serendipilyst.business import (
    anchor_flag as anchor_business_flag,
    list_flags as list_business_flags,
    list_nodes as list_business_nodes,
    retract_flag as retract_business_flag,
    retract_node as retract_business_node,
    upsert_node as upsert_business_node,
)
from shadenet.serendipilyst.personal import (
    list_flags as list_personal_flags,
    open_flags as open_personal_flags,
    retract_flag as retract_personal_flag,
    upsert_flag as upsert_personal_flag,
)
from shadenet.serendipilyst.store import FlagError, FlagStore

__all__ = [
    "FlagError",
    "FlagStore",
    "anchor_business_flag",
    "apply_deal",
    "apply_upsert",
    "counsel",
    "exposures",
    "get_store",
    "introduce",
    "oblige",
    "list_business_flags",
    "map_pins",
    "list_personal_flags",
    "open_personal_flags",
    "retract_business_flag",
    "retract_business_node",
    "pay",
    "release",
    "retract_personal_flag",
    "upsert_business_node",
    "upsert_personal_flag",
    "use_chat",
    "use_store",
]

_default: FlagStore | None = None
_chat: Any = None

_FORBIDDEN = {
    "price", "fee", "fees", "escrow", "payment", "currency", "stripe",
    "legal_name", "legalName", "email", "phone",
}


def use_store(store: FlagStore | None) -> None:
    """Install the process store used by ``apply_upsert``. ``None`` clears it."""
    global _default
    _default = store


def use_chat(conn: Any) -> None:
    """Install the chat connection for a private room. ``None`` keeps the room id only."""
    global _chat
    _chat = conn


def get_chat() -> Any:
    return _chat


def get_store() -> FlagStore:
    """Return the process store, creating an in-memory one on first use."""
    global _default
    if _default is None:
        _default = FlagStore(":memory:")
    return _default


def exposures(store: FlagStore | None = None) -> list[dict[str, Any]]:
    """Active offers collected from personal flags and business flags.

    A personal flag with no offer is a directory record, not an exposure.
    When ``link_postings`` is false the offer is still listed, without the
    flag id, so the posting is not tied back to the profile.
    """
    db = store or get_store()
    rows: list[dict[str, Any]] = []
    for flag in list_personal_flags(db, active_only=True):
        if not flag.get("offer_title"):
            continue
        row = {
            "kind": "personal",
            "holder": flag["holder"],
            "flag_id": flag["id"] if flag["link_postings"] else None,
            "title": flag["offer_title"],
            "body": flag["offer_body"],
            "skills": flag["skills"],
            "anonymous": flag["anonymous"] or not flag["link_postings"],
            "inbox": flag["owner"],
        }
        rows.append(row)
    for flag in list_business_flags(db, active_only=True):
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


def _public_profile(pin: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    """Intents and the three lines are flag content. Ratings and amounts are not."""
    if row.get("intents"):
        pin["intents"] = row["intents"]
    for key in ("good_at", "enjoy", "refuse"):
        if row.get(key):
            pin[key] = row[key]
    return pin


def map_pins(store: FlagStore | None = None) -> list[dict[str, Any]]:
    """Flags whose place is public. An unlisted flag is left out, place and all."""
    db = store or get_store()
    pins: list[dict[str, Any]] = []
    for flag in list_personal_flags(db, active_only=True):
        if not flag["listed"]:
            continue
        pins.append(_public_profile({
            "id": flag["id"],
            "kind": "personal",
            "holder": flag["holder"],
            "name": flag["display_name"],
            "place_id": flag["place_id"],
            "appearance": flag["appearance"],
        }, flag))
    for node in list_business_nodes(db, active_only=True):
        if not node["listed"]:
            continue
        pins.append(_public_profile({
            "id": node["id"],
            "kind": "business_node",
            "name": node["name"],
            "place_id": node["place_id"],
            "appearance": node["appearance"],
        }, node))
    return pins


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _leaks(value: Any) -> bool:
    if isinstance(value, dict):
        if _FORBIDDEN.intersection(value):
            return True
        return any(_leaks(item) for item in value.values())
    if isinstance(value, list):
        return any(_leaks(item) for item in value)
    return False


def apply_upsert(args: dict[str, Any], store: FlagStore | None = None) -> dict[str, Any]:
    """Dispatch one ``flags.upsert`` payload. Returns the command-engine shape."""
    leaked = _leaks(args)
    if leaked:
        return {
            "ok": False,
            "error": {
                "code": "schema_invalid",
                "message": "flags carry no payment or legal-identity fields",
            },
        }
    db = store or get_store()
    kind = args.get("kind")
    actor = str(args.get("actor") or "")
    try:
        if kind == "personal":
            human = args.get("human")
            steward = args.get("steward")
            if isinstance(human, dict) and isinstance(steward, dict):
                result = open_personal_flags(db, actor=actor, human=human, steward=steward)
            elif args.get("holder"):
                listed, place_id, order = omitted_listing(args)
                result = upsert_personal_flag(
                    db,
                    actor=actor,
                    holder=str(args.get("holder")),
                    display_name=args.get("display_name") or args.get("displayName") or "",
                    counterpart_name=args.get("counterpart_name") or args.get("counterpartName"),
                    flag_id=args.get("id") or args.get("flag_id"),
                    bio=args.get("bio") or "",
                    declarations=args.get("declarations"),
                    pgp=args.get("pgp"),
                    availability=args.get("availability"),
                    skills=args.get("skills"),
                    offer_title=args.get("offer_title") or args.get("offerTitle"),
                    offer_body=args.get("offer_body") or args.get("offerBody"),
                    link_postings=_as_bool(args.get("link_postings", args.get("linkPostings")), False),
                    anonymous=_as_bool(args.get("anonymous"), True),
                    listed=listed,
                    place_id=place_id,
                    appearance=args.get("appearance"),
                    order=order,
                )
            else:
                raise FlagError(
                    "schema_invalid",
                    "a personal flag opens a human flag and a steward flag",
                )
        elif kind == "business_node":
            listed, place_id, order = omitted_listing(args)
            result = upsert_business_node(
                db,
                actor=actor,
                name=args.get("name") or "",
                node_id=args.get("id") or args.get("node_id") or args.get("nodeId"),
                venue_id=args.get("venue_id") or args.get("venueId"),
                anonymous=_as_bool(args.get("anonymous"), True),
                listed=listed,
                place_id=place_id,
                appearance=args.get("appearance"),
                order=order,
            )
        elif kind == "business_flag":
            result = anchor_business_flag(
                db,
                actor=actor,
                node_id=args.get("node_id") or args.get("nodeId") or "",
                title=args.get("title") or "",
                body=args.get("body") or "",
                flag_id=args.get("id") or args.get("flag_id"),
                skills=args.get("skills"),
                anonymous=_as_bool(args.get("anonymous"), True),
            )
        else:
            return {
                "ok": False,
                "error": {
                    "code": "schema_invalid",
                    "message": "kind must be personal, business_node, or business_flag",
                },
            }
    except FlagError as exc:
        return {"ok": False, "error": {"code": exc.code, "message": str(exc)}}
    return {"ok": True, "result": result}


def apply_deal(args: dict[str, Any], store: FlagStore | None = None) -> dict[str, Any]:
    """Interest, the Monero obligation, and the private counsel after it."""
    if _leaks(args):
        return {
            "ok": False,
            "error": {
                "code": "schema_invalid",
                "message": "flags carry no payment or legal-identity fields",
            },
        }
    db = store or get_store()
    action = str(args.get("action") or "")
    actor = str(args.get("actor") or "")
    flag_id = str(args.get("flag_id") or args.get("flagId") or "")
    obligation_id = str(args.get("obligation_id") or args.get("obligationId") or "")
    try:
        if action == "interest":
            result = introduce(
                db, actor=actor, flag_id=flag_id,
                sentence=str(args.get("sentence") or ""), chat=get_chat(),
            )
        elif action == "accord":
            step = str(args.get("step") or "read")
            if step == "confirm":
                result = confirm_accord(db, actor=actor, flag_id=flag_id)
            elif step == "read":
                handed = any(str(args.get(key) or "").strip() for key in ("give", "get"))
                if handed or args.get("amount") not in (None, ""):
                    raise FlagError("schema_invalid", "I read the room. Don't hand me the price.")
                result = read_accord(db, actor=actor, flag_id=flag_id, chat=get_chat())
            else:
                raise FlagError("schema_invalid", "step must be read or confirm")
        elif action == "oblige":
            result = oblige(
                db, actor=actor, flag_id=flag_id,
                sentence=str(args.get("sentence") or ""),
                amount=args.get("amount"),
                room_id=args.get("room_id") or args.get("roomId"),
            )
        elif action == "pay":
            result = pay(
                db, actor=actor, obligation_id=obligation_id,
                tip=args.get("tip"), personal=args.get("personal"),
                product=args.get("product"), word=args.get("word"),
            )
        elif action == "release":
            result = release(
                db, actor=actor, obligation_id=obligation_id,
                tip=args.get("tip"), personal=args.get("personal"),
                product=args.get("product"), word=args.get("word"),
            )
        elif action == "counsel":
            result = counsel(db, actor=actor)
        else:
            raise FlagError(
                "schema_invalid",
                "action must be interest, accord, oblige, pay, release, or counsel",
            )
    except FlagError as exc:
        return {"ok": False, "error": {"code": exc.code, "message": str(exc)}}
    return {"ok": True, "result": result}
