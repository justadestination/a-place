"""Personal flags: one for the human, one for the Steward.

Both flags belong to the same Steward (``owner``) and point at each other.
Each keeps its own pseudonym, bio, skills, availability, marks, and
optional offer. The Steward flag shows a public address, and that address
is a relay: the Steward's own address never leaves the server.

A write changes only the fields it names. ``link_postings`` decides whether
an offer points back at its flag. ``listed`` puts the flag's place on the
WorldSum sheet. Real names, mail, and phone numbers are refused.
"""

from __future__ import annotations

import json
from typing import Any

from shadenet.serendipilyst import policy
from shadenet.serendipilyst.fields import KEEP, actor as check_actor, as_bool, canon, given, skills, strings, text
from shadenet.serendipilyst.flash import settle_flash
from shadenet.serendipilyst.intents import LINES, settle_profile
from shadenet.serendipilyst.relay import relay_for
from shadenet.serendipilyst.store import FlagError, FlagStore, load_obj, loads, new_id, now_iso

HOLDERS = ("human", "steward")
PGP_LIMIT = 8000
FIELDS = (
    "display_name", "bio", "declarations", "pgp", "availability", "skills",
    "offer_title", "offer_body", "link_postings", "anonymous",
    "listed", "place_id", "appearance", "order",
    "intents", "good_at", "enjoy", "refuse",
)


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
        "address": row["address"] or "",
        "pgp": row["pgp"] or "",
        "availability": loads(row["availability"]),
        "skills": loads(row["skills"]),
        "offer_title": row["offer_title"] or "",
        "offer_body": row["offer_body"] or "",
        "offered_at": row["offered_at"] or "",
        "link_postings": bool(row["link_postings"]),
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


def _by_holder(store: FlagStore, owner: str, holder: str):
    return store.query_one(
        "SELECT * FROM personal_flags WHERE owner = ? AND holder = ?",
        (owner, holder),
    )


def _public_address(store: FlagStore, owner: str, holder: str) -> str:
    """The Steward flag shows a relay. The human flag shows no address."""
    if holder != "steward":
        return ""
    return relay_for(store, ref=f"profile:{owner}", target=owner)


def _link_pair(store: FlagStore, owner: str) -> None:
    human = _by_holder(store, owner, "human")
    steward = _by_holder(store, owner, "steward")
    if human is None or steward is None:
        return
    store.execute("UPDATE personal_flags SET linked_flag_id = ? WHERE id = ?", (steward["id"], human["id"]))
    store.execute("UPDATE personal_flags SET linked_flag_id = ? WHERE id = ?", (human["id"], steward["id"]))


def _blank_flag(store: FlagStore, owner: str, holder: str, display_name: str) -> None:
    """The other flag, opened with a name and nothing else."""
    stamp = now_iso()
    store.execute(
        """
        INSERT INTO personal_flags (
            id, owner, holder, linked_flag_id, display_name, address, status, created_at, updated_at
        ) VALUES (?, ?, ?, '', ?, ?, 'active', ?, ?)
        """,
        (new_id("flg"), owner, holder, display_name, _public_address(store, owner, holder), stamp, stamp),
    )


def _current(store: FlagStore, owner: str, holder: str, flag_id: str | None):
    if not flag_id:
        return _by_holder(store, owner, holder)
    row = store.query_one("SELECT * FROM personal_flags WHERE id = ?", (flag_id,))
    if row is None:
        raise FlagError("not_found", f"personal flag {flag_id} does not exist")
    if row["owner"] != owner:
        raise FlagError("scope_denied", "only the owner can update this flag")
    if row["holder"] != holder:
        raise FlagError("schema_invalid", "flag belongs to the other holder")
    return row


def _pick(changes: dict[str, Any], key: str, stored: Any, clean) -> Any:
    """The cleaned new value when the write names ``key``, else the stored one."""
    if key in changes and given(changes[key]):
        return clean(changes[key])
    return stored


def upsert_flag(
    store: FlagStore,
    *,
    actor: str,
    holder: str,
    flag_id: str | None = None,
    counterpart_name: str | None = None,
    **changes: Any,
) -> dict[str, Any]:
    """Create one flag, or change the fields a write names.

    ``changes`` takes the names in ``FIELDS``. A name left out keeps its
    stored value; an empty value clears it. The first flag a Steward opens
    also opens the other one, named by ``counterpart_name``.
    """
    owner = check_actor(actor)
    who = _holder(holder)
    unknown = set(changes) - set(FIELDS)
    if unknown:
        raise FlagError("schema_invalid", f"a personal flag has no {sorted(unknown)[0]}")

    with store.transaction():
        current = _current(store, owner, who, flag_id)
        cur = _row(current) if current is not None else None

        name = _pick(changes, "display_name", cur and cur["display_name"],
                     lambda v: text(v, "display_name", 80, required=True))
        if not name:
            raise FlagError("schema_invalid", "display_name is required")
        about = _pick(changes, "bio", cur["bio"] if cur else "", lambda v: text(v, "bio", 2000))
        decls = _pick(changes, "declarations", cur["declarations"] if cur else [],
                      lambda v: strings(v, "declarations", 12, 280))
        slots = _pick(changes, "availability", cur["availability"] if cur else [],
                      lambda v: strings(v, "availability", 12, 80))
        tags = _pick(changes, "skills", cur["skills"] if cur else [], skills)
        key = _pick(changes, "pgp", cur["pgp"] if cur else "", lambda v: text(v, "pgp", PGP_LIMIT))
        title = _pick(changes, "offer_title", cur["offer_title"] if cur else "",
                      lambda v: text(v, "offer_title", 160))
        body = _pick(changes, "offer_body", cur["offer_body"] if cur else "",
                     lambda v: text(v, "offer_body", 4000))
        if bool(title) != bool(body):
            raise FlagError("schema_invalid", "an offer needs both a title and a body")
        linked = _pick(changes, "link_postings", cur["link_postings"] if cur else False,
                       lambda v: as_bool(v, False))
        hidden = _pick(changes, "anonymous", cur["anonymous"] if cur else True, lambda v: as_bool(v, True))

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
        # Saving a listing or an offer renews it. A new one has to fit the limits.
        renewing_place = on_map and (not cur or not cur["listed"] or "listed" in changes or bool(changes.get("order")))
        listed_at = stamp if renewing_place else (cur["listed_at"] if cur and on_map else None)
        offer_changed = bool(title) and (not cur or (title, body) != (cur["offer_title"], cur["offer_body"])
                                          or "offer_title" in changes)
        offered_at = stamp if offer_changed else (cur["offered_at"] if cur and title else None)
        adding = 0
        if on_map and not (cur and cur["listed"] and policy.fresh(cur["listed_at"])):
            adding += 1
        if title and not (cur and cur["offer_title"] and policy.fresh(cur["offered_at"])):
            adding += 1
        policy.admit(store, owner, adding=adding)

        other = _by_holder(store, owner, _other(who))
        if current is None and other is None:
            other_name = text(counterpart_name or "", "counterpart_name", 80, required=True)
            _blank_flag(store, owner, _other(who), other_name)

        values = {
            "display_name": name, "bio": about, "declarations": json.dumps(decls),
            "address": _public_address(store, owner, who), "pgp": key or None,
            "availability": json.dumps(slots), "skills": json.dumps(tags),
            "offer_title": title or None, "offer_body": body or None, "offered_at": offered_at or None,
            "link_postings": int(bool(linked)), "anonymous": int(bool(hidden)),
            "listed": int(on_map), "listed_at": listed_at or None, "place_id": place or None,
            "appearance": look, "intents": json.dumps(marks), **lines,
            "status": "active", "updated_at": stamp,
        }
        if current is None:
            saved_id = new_id("flg")
            columns = ["id", "owner", "holder", "linked_flag_id", "created_at", *values]
            store.execute(
                f"INSERT INTO personal_flags ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                (saved_id, owner, who, "", stamp, *values.values()),
            )
        else:
            saved_id = current["id"]
            assignments = ", ".join(f"{column} = ?" for column in values)
            store.execute(
                f"UPDATE personal_flags SET {assignments} WHERE id = ?",
                (*values.values(), saved_id),
            )
        _link_pair(store, owner)
        return _row(store.query_one("SELECT * FROM personal_flags WHERE id = ?", (saved_id,)))


def open_flags(store: FlagStore, *, actor: str, human: dict, steward: dict) -> dict[str, Any]:
    """Open or change both flags in one write. Neither flag is optional.

    If either side is refused, neither is saved.
    """
    if not isinstance(human, dict) or not isinstance(steward, dict):
        raise FlagError("schema_invalid", "a personal flag opens a human flag and a steward flag")
    human, steward = canon(human), canon(steward)
    with store.transaction():
        human_flag = upsert_flag(
            store,
            actor=actor,
            holder="human",
            flag_id=human.get("flag_id"),
            counterpart_name=steward.get("display_name") or "",
            **{k: v for k, v in human.items() if k != "flag_id"},
        )
        steward_flag = upsert_flag(
            store,
            actor=actor,
            holder="steward",
            flag_id=steward.get("flag_id"),
            **{k: v for k, v in steward.items() if k != "flag_id"},
        )
    return {"human": human_flag, "steward": steward_flag}


def list_flags(store: FlagStore, *, active_only: bool = True) -> list[dict[str, Any]]:
    where = "WHERE status = 'active'" if active_only else ""
    rows = store.query_all(f"SELECT * FROM personal_flags {where} ORDER BY updated_at DESC")
    return [_row(row) for row in rows]


def retract_flag(store: FlagStore, *, actor: str, flag_id: str) -> dict[str, Any]:
    """Take one flag down. The other flag in the pair stays."""
    owner = check_actor(actor)
    with store.transaction():
        current = store.query_one("SELECT * FROM personal_flags WHERE id = ?", (flag_id,))
        if current is None:
            raise FlagError("not_found", f"personal flag {flag_id} does not exist")
        if current["owner"] != owner:
            raise FlagError("scope_denied", "only the owner can retract this flag")
        store.execute(
            "UPDATE personal_flags SET status = 'retracted', updated_at = ? WHERE id = ?",
            (now_iso(), flag_id),
        )
        return _row(store.query_one("SELECT * FROM personal_flags WHERE id = ?", (flag_id,)))
