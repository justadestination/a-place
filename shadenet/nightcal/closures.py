"""Rooms a public notice says have closed.

OpenStreetMap still tags several of these as a bar or a pub. The map is
not a liveness check, so the rail asks this list before it shows a room.
The rows stay in the store. A later notice that one reopened replaces
the citation instead of deleting the room.
"""

from __future__ import annotations

from shadenet.towncrier.entities import KIND_OTHER, add_item, ensure_entity
from shadenet.towncrier.store import Store

# Spoken names are what the rail says. The match name is the venue row.
CITED = (
    {
        "name": "The Rusty Shamrock",
        "spoken": "The Rusty Shamrock",
        "source_url": "https://news.example.org/reports/downtown-venues-closures/",
        "note": "Named, in a December 2019 report, among downtown rooms that had already closed.",
    },
    {
        "name": "The Obsidian Room",
        "spoken": "the Obsidian Room",
        "source_url": "https://news.example.org/reports/downtown-venues-closures/",
        "note": "Closed at the end of October 2019.",
    },
    {
        "name": "The Iron Anchor",
        "spoken": "the Iron Anchor",
        "source_url": "https://gazette.example.org/reports/iron-anchor-closure/",
        "note": "Closed March 1, 2024.",
    },
    {
        "name": "The Sol Cantina",
        "spoken": "The Sol Cantina",
        "source_url": "https://gazette.example.org/reports/sol-cantina-closure/",
        "note": "Closed in March 2025.",
    },
)

_BY_NAME = {row["name"].casefold(): row for row in CITED}


def is_closed(name: str) -> bool:
    return (name or "").casefold() in _BY_NAME


def note_for(names: list[str]) -> str:
    """One sentence for the rooms this store actually had, then hid."""
    present = {name.casefold() for name in names}
    spoken = [row["spoken"] for row in CITED if row["name"].casefold() in present]
    if not spoken:
        return ""
    if len(spoken) == 1:
        label = spoken[0][:1].upper() + spoken[0][1:]
        return f"{label} is off the rail. A public notice says it closed."
    if len(spoken) == 2:
        body = f"{spoken[0]} and {spoken[1]}"
    else:
        body = ", ".join(spoken[:-1]) + ", and " + spoken[-1]
    body = body[:1].upper() + body[1:]
    return f"{body} are off the rail. A public notice says each one closed."


def cite_closures(store: Store) -> None:
    """Attach the notice to the venue entity, when that room is in the store."""
    city = store.one(
        "SELECT id FROM entities WHERE kind = 'city' AND name = ?",
        ("Metropolis",),
    )
    if city is None:
        return
    for row in CITED:
        venue = store.one("SELECT id FROM venues WHERE name = ?", (row["name"],))
        if venue is None:
            continue
        entity_id = ensure_entity(
            store, name=row["name"], kind="venue", parent_id=city["id"], role="host",
        )
        add_item(
            store, entity_id=entity_id, kind=KIND_OTHER, value="closed",
            display=row["note"], source_id="press:" + row["name"].casefold(),
            source_url=row["source_url"], citation_kind="html", excerpt=row["note"],
        )
