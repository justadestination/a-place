"""The Monero obligation that can follow an accord.

When both people have confirmed a price in XMR, the buyer can oblige
themselves to the platform for that amount. The steps:

1. ``oblige``: the buyer takes on the debt for the confirmed terms.
2. ``pay``: the buyer says they paid the platform, with an optional tip.
3. ``release``: the platform's debt to the seller is released.

This module keeps the record only. It does not build a payable address,
watch a wallet, or broadcast a transfer, so ``paid`` is what the buyer
says until a wallet confirms it.

Who may release, and on what evidence, is not decided yet (see
``may_release``). Until it is, release is refused and the money stays
with the platform.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from shadenet.serendipilyst.accord import _room
from shadenet.serendipilyst.fields import actor as check_actor
from shadenet.serendipilyst.store import FlagError, FlagStore, new_id, now_iso

XMR_UNITS = {"XMR", "MONERO"}


def xmr(value: Any, label: str, *, required: bool) -> str | None:
    """A Monero amount: positive, at most 12 decimal places (one piconero)."""
    if value is None or value == "":
        if required:
            raise FlagError("schema_invalid", f"{label} is required")
        return None
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation:
        raise FlagError("schema_invalid", f"{label} must be a Monero amount") from None
    exponent = number.as_tuple().exponent if number.is_finite() else 0
    if not number.is_finite() or number < 0 or number > Decimal("1000000") or (
        isinstance(exponent, int) and exponent < -12
    ):
        raise FlagError("schema_invalid", f"{label} must be a Monero amount")
    if number == 0:
        if required:
            raise FlagError("schema_invalid", f"{label} must be a Monero amount")
        return None
    rendered = format(number, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _view(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "room_id": row["room_id"],
        "item": row["item"],
        "amount_xmr": row["amount_xmr"],
        "state": row["state"],
        "paid_tip_xmr": row["paid_tip_xmr"] or "",
        "released_tip_xmr": row["released_tip_xmr"] or "",
    }


def open_obligation(store: FlagStore, room_id: str) -> Any:
    """The obligation in a room that hasn't been released, if any."""
    return store.query_one(
        "SELECT * FROM room_obligations WHERE room_id = ? AND state != 'released'",
        (room_id,),
    )


def oblige(
    store: FlagStore,
    *,
    actor: str,
    terms: str,
    room_id: str = "",
    flag_id: str = "",
) -> dict[str, Any]:
    """The buyer owes the platform the confirmed XMR price."""
    who = check_actor(actor)
    intro = _room(store, who, room_id, flag_id)
    if who != intro["buyer"]:
        raise FlagError("scope_denied", "only the buyer takes on the obligation")
    with store.transaction():
        accord = store.query_one("SELECT * FROM room_accords WHERE room_id = ?", (intro["room_id"],))
        if accord is None or accord["state"] != "accorded":
            raise FlagError(
                "schema_invalid",
                "both of you have to confirm what changes hands and the price",
            )
        if not terms or terms != accord["terms"]:
            raise FlagError("stale_terms", "Those aren't the terms you both confirmed.")
        if accord["unit"].upper() not in XMR_UNITS:
            raise FlagError("schema_invalid", "That price isn't in XMR. Settle it between you.")
        if open_obligation(store, intro["room_id"]) is not None:
            raise FlagError("schema_invalid", "there is already an open obligation in this room")
        amount = xmr(accord["amount"], "the price", required=True)
        saved = new_id("obl")
        stamp = now_iso()
        store.execute(
            """
            INSERT INTO room_obligations (
                id, room_id, buyer, seller, item, amount_xmr, terms, state, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'obliged', ?, ?)
            """,
            (saved, intro["room_id"], intro["buyer"], intro["seller"], accord["item"],
             amount, terms, stamp, stamp),
        )
        row = store.query_one("SELECT * FROM room_obligations WHERE id = ?", (saved,))
    view = _view(row)
    view["reply"] = f"You owe the platform {amount} XMR for {accord['item']}."
    return view


def _step(store: FlagStore, obligation_id: str, *, before: str, after: str, column: str, tip: str | None) -> Any:
    """Move one obligation forward, only if it is still where we found it."""
    moved = store.execute(
        f"UPDATE room_obligations SET state = ?, {column} = ?, updated_at = ? WHERE id = ? AND state = ?",
        (after, tip, now_iso(), obligation_id, before),
    )
    if moved.rowcount != 1:
        raise FlagError("schema_invalid", "that step has already been taken")
    return store.query_one("SELECT * FROM room_obligations WHERE id = ?", (obligation_id,))


def _load(store: FlagStore, obligation_id: str):
    row = store.query_one("SELECT * FROM room_obligations WHERE id = ?", (obligation_id,))
    if row is None:
        raise FlagError("not_found", "that obligation does not exist")
    return row


def pay(store: FlagStore, *, actor: str, obligation_id: str, tip: Any = None) -> dict[str, Any]:
    """The buyer says they paid the platform. A tip is optional."""
    who = check_actor(actor)
    tipped = xmr(tip, "the tip", required=False)
    with store.transaction():
        row = _load(store, obligation_id)
        if who != row["buyer"]:
            raise FlagError("scope_denied", "only the buyer pays")
        row = _step(store, obligation_id, before="obliged", after="paid", column="paid_tip_xmr", tip=tipped)
    view = _view(row)
    view["reply"] = f"Paid {row['amount_xmr']} XMR to the platform for {row['item']}." + (
        " Tip noted." if tipped else ""
    )
    return view


def may_release(obligation: dict[str, Any], actor: str) -> None:
    """Decide whether ``actor`` may release ``obligation`` to the seller.

    Raise FlagError to refuse. Return to allow.

    Not decided yet. If the buyer releases, a buyer can simply not; if the
    seller releases, a seller can take the money and not hand over; the
    operator has no way to confirm a hand-over. A dead drop that proves the
    hand-over is the likely answer, and its proof would be checked here.
    """
    raise FlagError(
        "release_undecided",
        "Release isn't settled yet. The money stays with the platform.",
    )


def release(store: FlagStore, *, actor: str, obligation_id: str, tip: Any = None) -> dict[str, Any]:
    """Release the platform's debt to the seller, when ``may_release`` allows it."""
    who = check_actor(actor)
    tipped = xmr(tip, "the tip", required=False)
    with store.transaction():
        row = _load(store, obligation_id)
        if who not in (row["buyer"], row["seller"]):
            raise FlagError("scope_denied", "that obligation isn't yours")
        if row["state"] != "paid":
            raise FlagError("schema_invalid", "it has to be paid before it is released")
        may_release(_view(row) | {"buyer": row["buyer"], "seller": row["seller"]}, who)
        row = _step(store, obligation_id, before="paid", after="released", column="released_tip_xmr", tip=tipped)
    view = _view(row)
    view["reply"] = f"Released to the seller. {row['item']}." + (" Tip noted." if tipped else "")
    return view
