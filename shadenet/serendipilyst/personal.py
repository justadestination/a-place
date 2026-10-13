"""Personal flags: one for the human, one for the Steward.

The spec also calls a flag an agent card. In this package the record is a
flag. The human and the Steward each have one. They share the Steward
address that writes and receives contact, and they point at each other.
They do not share a name, a bio, or an offer.

Spec §3.A. A flag shows a pseudonym, declarations, availability, and skill
tags. The Steward flag also shows its A2A address. ``link_postings`` chooses
whether an offer on that flag points back at it. ``listed`` is separate:
only a listed flag publishes a WorldSum place. Real names, mail, and
phone numbers are not fields on either flag.
"""

from __future__ import annotations

import json
import re
from typing import Any

from shadenet.serendipilyst.flash import omitted_listing, settle_flash
from shadenet.serendipilyst.intents import omitted_profile, settle_profile
from shadenet.serendipilyst.store import FlagError, FlagStore, load_obj, loads, new_id, now_iso

_A2A = re.compile(r"^a2a://agent/[A-Za-z0-9_.:-]{1,80}$")
_TAG = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")
HOLDERS = ("human", "steward")


def _actor(actor: str) -> str:
    if not _A2A.match(actor or ""):
        raise FlagError("scope_denied", "actor must be an a2a://agent/ address")
    return actor


def _text(value: str, label: str, limit: int, *, required: bool = False) -> str:
    text = (value or "").strip()
    if required and not text:
        raise FlagError("schema_invalid", f"{label} is required")
    if len(text) > limit:
        raise FlagError("schema_invalid", f"{label} is longer than {limit} characters")
    return text


def _strings(values: list | None, label: str, limit: int, item_limit: int) -> list[str]:
    if not values:
        return []
    if not isinstance(values, list):
        raise FlagError("schema_invalid", f"{label} must be a list")
    out: list[str] = []
    for raw in values:
        text = str(raw).strip()
        if not text:
            continue
        if len(text) > item_limit:
            raise FlagError("schema_invalid", f"{label} entry is too long")
        if text not in out:
            out.append(text)
    if len(out) > limit:
        raise FlagError("schema_invalid", f"at most {limit} {label}")
    return out


def _skills(values: list | None) -> list[str]:
    tags = []
    for raw in _strings(values, "skills", 12, 32):
        tag = raw.lstrip("#").lower()
        if not _TAG.fullmatch(tag):
            raise FlagError("schema_invalid", f"skill tag {raw!r} is not a short label")
        if tag not in tags:
            tags.append(tag)
    return tags


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _holder(value: str) -> str:
    if value not in HOLDERS:
        raise FlagError("schema_invalid", "holder must be human or steward")
    return value


def _other(holder: str) -> str:
    return "steward" if holder == "human" else "human"


def _row(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "kind": "personal",
        "holder": row["holder"],
        "owner": row["owner"],
        "linked_flag_id": row["linked_flag_id"] or "",
        "display_name": row["display_name"],
        "bio": row["bio"],
        "declarations": loads(row["declarations"]),
        "address": row["address"],
        "pgp": row["pgp"] or "",
        "availability": loads(row["availability"]),
        "skills": loads(row["skills"]),
        "offer_title": row["offer_title"] or "",
        "offer_body": row["offer_body"] or "",
        "link_postings": bool(row["link_postings"]),
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


def _by_holder(store: FlagStore, owner: str, holder: str):
    return store.query_one(
        "SELECT * FROM personal_flags WHERE owner = ? AND holder = ?",
        (owner, holder),
    )


def _link_pair(store: FlagStore, owner: str) -> None:
    human = _by_holder(store, owner, "human")
    steward = _by_holder(store, owner, "steward")
    if human is None or steward is None:
        return
    stamp = now_iso()
    store.execute(
        "UPDATE personal_flags SET linked_flag_id = ?, updated_at = ? WHERE id = ?",
        (steward["id"], stamp, human["id"]),
    )
    store.execute(
        "UPDATE personal_flags SET linked_flag_id = ?, updated_at = ? WHERE id = ?",
        (human["id"], stamp, steward["id"]),
    )


def _blank_flag(store: FlagStore, owner: str, holder: str, display_name: str) -> str:
    """The other flag, opened with a name and nothing else."""
    saved_id = new_id("flg")
    stamp = now_iso()
    address = owner if holder == "steward" else ""
    store.execute(
        """
        INSERT INTO personal_flags (
            id, owner, holder, linked_flag_id, display_name, bio, declarations,
            address, pgp, availability, skills, offer_title, offer_body,
            link_postings, anonymous, listed, place_id, appearance,
            status, created_at, updated_at
        ) VALUES (?, ?, ?, '', ?, '', '[]', ?, NULL, '[]', '[]', NULL, NULL, 0, 1, 0, NULL, NULL, 'active', ?, ?)
        """,
        (saved_id, owner, holder, display_name, address, stamp, stamp),
    )
    return saved_id


def upsert_flag(
    store: FlagStore,
    *,
    actor: str,
    display_name: str,
    holder: str,
    flag_id: str | None = None,
    counterpart_name: str | None = None,
    bio: str = "",
    declarations: list | None = None,
    pgp: str | None = None,
    availability: list | None = None,
    skills: list | None = None,
    offer_title: str | None = None,
    offer_body: str | None = None,
    link_postings: bool = False,
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
    """Create or replace one flag. The first flag opened also opens the other.

    ``holder`` is ``human`` or ``steward``. The Steward address is the owner
    of both. On the first write, ``counterpart_name`` is the other flag's
    pseudonym. Later writes touch only the named holder. A write replaces
    the flag. An order changes only the parts it names, and it leaves the
    listing alone unless it says to list or pull.
    """
    owner = _actor(actor)
    who = _holder(holder)
    name = _text(display_name, "display_name", 80, required=True)
    about = _text(bio, "bio", 2000)
    decls = _strings(declarations, "declarations", 12, 280)
    slots = _strings(availability, "availability", 12, 80)
    tags = _skills(skills)
    key = _text(pgp or "", "pgp", 500)
    title = _text(offer_title or "", "offer_title", 160)
    body = _text(offer_body or "", "offer_body", 4000)
    if bool(title) != bool(body):
        raise FlagError("schema_invalid", "an offer needs both a title and a body")

    current = None
    if flag_id:
        current = store.query_one("SELECT * FROM personal_flags WHERE id = ?", (flag_id,))
        if current is None:
            raise FlagError("not_found", f"personal flag {flag_id} does not exist")
        if current["owner"] != owner:
            raise FlagError("scope_denied", "only the owner can update this flag")
        if current["holder"] != who:
            raise FlagError("schema_invalid", "flag belongs to the other holder")
    else:
        current = _by_holder(store, owner, who)

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

    other = _by_holder(store, owner, _other(who))
    if current is None and other is None:
        other_name = _text(counterpart_name or "", "counterpart_name", 80, required=True)
        _blank_flag(store, owner, _other(who), other_name)

    address = owner if who == "steward" else ""
    stamp = now_iso()
    fields = (
        name, about, json.dumps(decls), address, key or None,
        json.dumps(slots), json.dumps(tags), title or None, body or None,
        int(bool(link_postings)), int(bool(anonymous)),
        int(on_map), place or None, look,
        json.dumps(marks), skilled, liked, refused, stamp,
    )
    if current is None:
        saved_id = new_id("flg")
        store.execute(
            """
            INSERT INTO personal_flags (
                id, owner, holder, linked_flag_id, display_name, bio, declarations,
                address, pgp, availability, skills, offer_title, offer_body,
                link_postings, anonymous, listed, place_id, appearance,
                intents, good_at, enjoy, refuse,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (saved_id, owner, who, *fields, stamp),
        )
    else:
        saved_id = current["id"]
        store.execute(
            """
            UPDATE personal_flags SET
                display_name = ?, bio = ?, declarations = ?, address = ?, pgp = ?,
                availability = ?, skills = ?, offer_title = ?, offer_body = ?,
                link_postings = ?, anonymous = ?, listed = ?, place_id = ?,
                appearance = ?, intents = ?, good_at = ?, enjoy = ?, refuse = ?,
                status = 'active', updated_at = ?
            WHERE id = ?
            """,
            (*fields, saved_id),
        )
    _link_pair(store, owner)
    row = store.query_one("SELECT * FROM personal_flags WHERE id = ?", (saved_id,))
    return _row(row)


def open_flags(
    store: FlagStore,
    *,
    actor: str,
    human: dict,
    steward: dict,
) -> dict[str, Any]:
    """Open or refresh both flags. Neither flag is optional."""
    if not isinstance(human, dict) or not isinstance(steward, dict):
        raise FlagError("schema_invalid", "a personal flag opens a human flag and a steward flag")
    human_listed, human_place, human_order = omitted_listing(human)
    steward_listed, steward_place, steward_order = omitted_listing(steward)
    human_intents, human_good, human_enjoy, human_refuse = omitted_profile(human)
    steward_intents, steward_good, steward_enjoy, steward_refuse = omitted_profile(steward)
    human_flag = upsert_flag(
        store,
        actor=actor,
        holder="human",
        display_name=human.get("display_name") or human.get("displayName") or "",
        counterpart_name=steward.get("display_name") or steward.get("displayName") or "",
        flag_id=human.get("id") or human.get("flag_id"),
        bio=human.get("bio") or "",
        declarations=human.get("declarations"),
        pgp=human.get("pgp"),
        availability=human.get("availability"),
        skills=human.get("skills"),
        offer_title=human.get("offer_title") or human.get("offerTitle"),
        offer_body=human.get("offer_body") or human.get("offerBody"),
        link_postings=_as_bool(human.get("link_postings", human.get("linkPostings")), False),
        anonymous=_as_bool(human.get("anonymous"), True),
        listed=human_listed,
        place_id=human_place,
        appearance=human.get("appearance"),
        order=human_order,
        intents=human_intents,
        good_at=human_good,
        enjoy=human_enjoy,
        refuse=human_refuse,
    )
    steward_flag = upsert_flag(
        store,
        actor=actor,
        holder="steward",
        display_name=steward.get("display_name") or steward.get("displayName") or "",
        flag_id=steward.get("id") or steward.get("flag_id"),
        bio=steward.get("bio") or "",
        declarations=steward.get("declarations"),
        pgp=steward.get("pgp"),
        availability=steward.get("availability"),
        skills=steward.get("skills"),
        offer_title=steward.get("offer_title") or steward.get("offerTitle"),
        offer_body=steward.get("offer_body") or steward.get("offerBody"),
        link_postings=_as_bool(steward.get("link_postings", steward.get("linkPostings")), False),
        anonymous=_as_bool(steward.get("anonymous"), True),
        listed=steward_listed,
        place_id=steward_place,
        appearance=steward.get("appearance"),
        order=steward_order,
        intents=steward_intents,
        good_at=steward_good,
        enjoy=steward_enjoy,
        refuse=steward_refuse,
    )
    return {"human": human_flag, "steward": steward_flag}


def list_flags(store: FlagStore, *, active_only: bool = True) -> list[dict[str, Any]]:
    if active_only:
        rows = store.query_all(
            "SELECT * FROM personal_flags WHERE status = 'active' ORDER BY updated_at DESC"
        )
    else:
        rows = store.query_all("SELECT * FROM personal_flags ORDER BY updated_at DESC")
    return [_row(row) for row in rows]


def retract_flag(store: FlagStore, *, actor: str, flag_id: str) -> dict[str, Any]:
    owner = _actor(actor)
    current = store.query_one("SELECT * FROM personal_flags WHERE id = ?", (flag_id,))
    if current is None:
        raise FlagError("not_found", f"personal flag {flag_id} does not exist")
    if current["owner"] != owner:
        raise FlagError("scope_denied", "only the owner can retract this flag")
    store.execute(
        "UPDATE personal_flags SET status = 'retracted', updated_at = ? WHERE id = ?",
        (now_iso(), flag_id),
    )
    row = store.query_one("SELECT * FROM personal_flags WHERE id = ?", (flag_id,))
    return _row(row)
