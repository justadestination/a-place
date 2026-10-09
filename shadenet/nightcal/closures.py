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
        "name": "Stout Brothers Irish Pub",
        "spoken": "Stout Brothers",
        "source_url": "https://www.sonomanews.com/article/business/santa-rosa-downtown-businesses-grapple-with-challenges-to-stay-afloat/",
        "note": "Named, in a December 2019 report, among downtown rooms that had already closed.",
    },
    {
        "name": "The Jade Room",
        "spoken": "the Jade Room",
        "source_url": "https://www.sonomanews.com/article/business/santa-rosa-downtown-businesses-grapple-with-challenges-to-stay-afloat/",
        "note": "Closed at the end of October 2019.",
    },
    {
        "name": "The Dirty",
        "spoken": "the Dirty",
        "source_url": "https://www.pressdemocrat.com/article/news/santa-rosa-dive-bar-the-dirty-to-close-march-1/",
        "note": "Closed March 1, 2024.",
    },
    {
        "name": "The Tipsy Taco Cantina",
        "spoken": "Tipsy Taco",
        "source_url": "https://www.pressdemocrat.com/article/north-bay/tipsy-taco-closure-santa-rosa/",
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
        ("Santa Rosa",),
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
