"""Relay addresses: the only contact address the public ever sees.

A relay alias stands in for a Steward address. The sheet shows the alias,
and the server delivers to the Steward behind it. Each alias has a ``ref``
naming what it stands for:

- ``profile:<owner>``: the Steward flag's public address.
- ``offer:<flag_id>:<digest>``: one personal offer. A new offer text gets a
  new alias, so an old posting cannot be matched to a new one.
- ``node:<node_id>``: a business node's inbox.

Aliases start with ``a2a://relay/`` and never pass the actor check, so
holding one lets you write to it and nothing else.
"""

from __future__ import annotations

import hashlib
import secrets

from shadenet.serendipilyst.store import FlagError, FlagStore, now_iso

PREFIX = "a2a://relay/"


def new_alias() -> str:
    return PREFIX + secrets.token_urlsafe(12)


def relay_for(store: FlagStore, *, ref: str, target: str) -> str:
    """Return the alias for ``ref``, creating it the first time."""
    with store.transaction():
        row = store.query_one("SELECT alias, target FROM relays WHERE ref = ?", (ref,))
        if row is not None:
            if row["target"] != target:
                store.execute("UPDATE relays SET target = ? WHERE ref = ?", (target, ref))
            return row["alias"]
        alias = new_alias()
        store.execute(
            "INSERT INTO relays (alias, ref, target, created_at) VALUES (?, ?, ?, ?)",
            (alias, ref, target, now_iso()),
        )
        return alias


def offer_ref(flag_id: str, title: str, body: str) -> str:
    digest = hashlib.sha256(f"{title}\n{body}".encode()).hexdigest()[:16]
    return f"offer:{flag_id}:{digest}"


def resolve(store: FlagStore, alias: str) -> dict[str, str]:
    """The Steward address and ref behind an alias. For delivery, never for display."""
    row = store.query_one("SELECT ref, target FROM relays WHERE alias = ?", (alias,))
    if row is None:
        raise FlagError("not_found", "nobody answers at that address")
    return {"ref": row["ref"], "target": row["target"]}
