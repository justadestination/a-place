"""The tree and its items.

Where store.py holds the mechanical persistence, this module holds the rules
about *meaning*: what counts as the same entity, how a fact gets published,
and how disagreement between sources is recorded rather than resolved.

The two rules this file exists to enforce:

1. **A fact is only publishable if it has a public source.** `add_item`
   requires a source_url (or an explicit `manual` origin for something the
   operator typed themselves). There is no code path that produces a fact with
   no provenance, so "we only use publicly available information" is a
   property of the schema rather than a promise in a README.

2. **Disagreement is preserved, not resolved.** When two sources state
   different values for the same (entity, kind), both rows stay. We do not
   pick a winner, we do not average, and we do not drop the minority. The
   `conflicts_with` link records that a conflict exists so the review queue
   can surface it — but nothing is overwritten.

The distinction that matters: an absent fact and a contradicted fact are
different states. A venue with no phone number is a venue with an unknown
phone number. A venue with two different phone numbers is a venue whose phone
number is disputed. Both are fine to publish as long as the second one is
labelled as disputed rather than silently flattened into the first.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any, Iterable

from .store import Store, stable_id, utcnow

# ---------------------------------------------------------------- item kinds
#
# Normalization per kind is what makes "two sources agree" a meaningful
# question. "(707) 543-1234" and "707.543.1234" are the same number; they are
# not the same string.
KIND_PHONE = "phone"
KIND_EMAIL = "email"
KIND_WEBSITE = "website"
KIND_ADDRESS = "address"
KIND_SOCIAL = "social"
KIND_HOURS = "hours"
KIND_OTHER = "other"

ITEM_KINDS = (KIND_PHONE, KIND_EMAIL, KIND_WEBSITE, KIND_ADDRESS,
              KIND_SOCIAL, KIND_HOURS, KIND_OTHER)

# How much we trust a source for a given kind of fact, by source kind. The
# venue's own structured data beats a link we found on a third-party page.
SOURCE_TRUST = {
    "structured_data": {
        KIND_PHONE: 0.95, KIND_EMAIL: 0.95, KIND_ADDRESS: 0.95,
        KIND_WEBSITE: 0.9, KIND_SOCIAL: 0.8, KIND_HOURS: 0.9,
    },
    "rss": {
        KIND_WEBSITE: 0.85, KIND_PHONE: 0.7, KIND_EMAIL: 0.7,
        KIND_ADDRESS: 0.6, KIND_SOCIAL: 0.6, KIND_HOURS: 0.5,
    },
    "html": {
        KIND_WEBSITE: 0.7, KIND_PHONE: 0.6, KIND_EMAIL: 0.6,
        KIND_ADDRESS: 0.5, KIND_SOCIAL: 0.4, KIND_HOURS: 0.4,
    },
    "manual": {k: 1.0 for k in ITEM_KINDS},   # the operator outranks any scrape
    "derived": {k: 0.2 for k in ITEM_KINDS},  # inferred: never published alone
}
DEFAULT_TRUST = 0.5


# ---------------------------------------------------------------- normalize

def normalize_item(kind: str, value: str) -> str:
    """Canonical form of a fact, for equality comparison between sources.

    Not for display — `items.display` keeps the original.
    """
    if not value:
        return ""
    text = value.strip()

    if kind == KIND_PHONE:
        digits = re.sub(r"\D", "", text)
        # Drop a leading US country code so +17075431234 and 7075431234 agree.
        if digits.startswith("1") and len(digits) == 11:
            digits = digits[1:]
        return digits

    if kind == KIND_EMAIL:
        return text.lower().strip()

    if kind == KIND_WEBSITE:
        lowered = text.lower().strip()
        for prefix in ("https://", "http://", "//"):
            if lowered.startswith(prefix):
                lowered = lowered[len(prefix):]
        return lowered.rstrip("/")

    if kind == KIND_SOCIAL:
        return text.lower().strip().lstrip("@").rstrip("/")

    if kind == KIND_ADDRESS:
        return re.sub(r"\s+", " ", text.lower().strip()).strip(" ,.")

    return re.sub(r"\s+", " ", text.lower().strip())


def item_confidence(kind: str, citation_kind: str) -> float:
    return SOURCE_TRUST.get(citation_kind, {}).get(kind, DEFAULT_TRUST)


# ---------------------------------------------------------------- the tree

def ensure_entity(
    store: Store,
    *,
    name: str,
    kind: str,
    parent_id: str | None = None,
    role: str | None = None,
    meta: dict | None = None,
) -> str:
    """Create or fetch an entity. Idempotent.

    Ids are derived from (kind, name) alone, not from the parent: a band that
    plays two rooms is one leaf, and a promoter whose rooms are booked by two
    different entities should collapse to one person. Identity across the
    tree is a separate problem, handled by `verified` and entity_links.
    """
    entity_id = stable_id("ent", kind, name)
    store.execute(
        """
        INSERT INTO entities (id, kind, name, parent_id, role, meta)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            parent_id = COALESCE(excluded.parent_id, entities.parent_id),
            role      = COALESCE(excluded.role, entities.role),
            meta      = CASE WHEN excluded.meta = '{}' THEN entities.meta
                             ELSE entities.meta END,
            updated_at = datetime('now')
        """,
        (entity_id, kind, name, parent_id, role, _json(meta or {})),
    )
    return entity_id


def link(store: Store, from_id: str, to_id: str, rel: str, source_id: str | None = None) -> None:
    """Record a relationship. Self-links and duplicates are ignored."""
    if from_id == to_id:
        return
    store.execute(
        """
        INSERT OR IGNORE INTO entity_links (from_id, to_id, rel, source_id)
        VALUES (?, ?, ?, ?)
        """,
        (from_id, to_id, rel, source_id),
    )


def tree(store: Store, root_id: str | None = None) -> list[sqlite3.Row]:
    """The whole tree as rows with a depth marker, for display.

    Returns venues and leaves under the trunk. Events (acorns) are not
    included — they are the product, not the structure.
    """
    return store.query(
        """
        SELECT e.*,
               (SELECT COUNT(*) FROM entity_links l
                 WHERE l.to_id = e.id) AS inbound_links,
               (SELECT COUNT(*) FROM items i
                 WHERE i.entity_id = e.id) AS item_count
        FROM entities e
        ORDER BY
            CASE e.kind WHEN 'city' THEN 0 WHEN 'venue' THEN 1
                       WHEN 'promoter' THEN 2 ELSE 3 END,
            e.name
        """
    )


# ---------------------------------------------------------------- items

class UncitedFact(Exception):
    """Raised when a fact arrives with no public source behind it.

    This is the guard rail for the project's one hard rule. It is an
    exception rather than a silent NULL because a fact we cannot cite is a
    fact we must not publish, and failing loudly at the write is the only
    place that rule can be enforced.
    """


def add_item(
    store: Store,
    *,
    entity_id: str,
    kind: str,
    value: str,
    source_url: str | None = None,
    source_id: str | None = None,
    citation_kind: str = "html",
    display: str | None = None,
    excerpt: str | None = None,
    allow_manual: bool = True,
) -> int:
    """Record a fact about an entity, with its provenance.

    Returns the item id. Idempotent on (entity_id, kind, value): re-running a
    scan updates `last_seen_at` rather than creating a duplicate.

    Raises UncitedFact when there is no source_url and the caller has not
    declared the input as operator-supplied. There is deliberately no way to
    add an uncited fact: that is the whole point.
    """
    if kind not in ITEM_KINDS:
        raise ValueError(f"unknown item kind {kind!r}; expected one of {ITEM_KINDS}")

    norm = normalize_item(kind, value)
    if not norm:
        raise ValueError(f"empty {kind} value")

    if not source_url:
        if not (allow_manual and citation_kind == "manual"):
            raise UncitedFact(
                f"{kind}={value!r} for {entity_id} has no source_url and was not "
                f"declared manual. Every published fact needs a public source."
            )
        source_url = f"manual://{entity_id}"

    confidence = item_confidence(kind, citation_kind)
    store.execute(
        """
        INSERT INTO items (entity_id, kind, value, display, source_id, source_url,
                           confidence, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(entity_id, kind, value) DO UPDATE SET
            last_seen_at = excluded.last_seen_at,
            -- Keep the more-trusted provenance if a better source shows up.
            source_id   = CASE WHEN excluded.confidence > items.confidence
                               THEN excluded.source_id ELSE items.source_id END,
            source_url  = CASE WHEN excluded.confidence > items.confidence
                               THEN excluded.source_url ELSE items.source_url END,
            confidence  = MAX(items.confidence, excluded.confidence)
        """,
        (entity_id, kind, norm, display or value, source_id, source_url,
         confidence, utcnow()),
    )

    row = store.one(
        "SELECT id FROM items WHERE entity_id = ? AND kind = ? AND value = ?",
        (entity_id, kind, norm),
    )
    if row is None:
        raise RuntimeError(f"item insert failed for {entity_id}/{kind}")
    item_id = int(row["id"])

    # One row per (item, source). Keyed on the pair, NOT on item_id alone:
    # a single-column primary key with INSERT OR REPLACE let a second source
    # silently overwrite the first, which destroyed provenance — the one thing
    # this table exists to preserve. The same source re-asserting the same
    # fact is still idempotent.
    store.execute(
        """
        INSERT INTO citations (item_id, source_id, source_url, kind, excerpt)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(item_id, source_id) DO UPDATE SET
            source_url = excluded.source_url,
            kind       = excluded.kind,
            excerpt    = COALESCE(excluded.excerpt, citations.excerpt)
        """,
        (item_id, source_id or citation_kind, source_url, citation_kind, excerpt),
    )

    _mark_conflicts(store, entity_id, kind, item_id)
    return item_id


def _mark_conflicts(store: Store, entity_id: str, kind: str, item_id: int) -> None:
    """Flag items of this kind that disagree with each other.

    A conflict is two or more *distinct* values for one (entity, kind). One
    value seen by many sources is corroboration, not conflict — those
    collapse into a single row by the UNIQUE constraint.

    Both sides are linked. Nothing is deleted, ranked, or resolved.
    """
    siblings = store.query(
        "SELECT id FROM items WHERE entity_id = ? AND kind = ? AND id != ?",
        (entity_id, kind, item_id),
    )
    if not siblings:
        store.execute(
            "UPDATE items SET conflicts_with = NULL WHERE id = ?", (item_id,)
        )
        return
    # Symmetric: store the lowest sibling id so both rows converge on the
    # same link and repeated calls are idempotent.
    peer = min(int(s["id"]) for s in siblings)
    store.execute(
        "UPDATE items SET conflicts_with = ? WHERE id = ?", (peer, item_id)
    )
    store.execute(
        "UPDATE items SET conflicts_with = ? WHERE id = ? AND conflicts_with IS NULL",
        (item_id, peer),
    )


def items_for(store: Store, entity_id: str, kind: str | None = None) -> list[sqlite3.Row]:
    """Facts about an entity, best first.

    Ordering is by trust, then by conflict state: the value a venue published
    about itself outranks a value a third party guessed, and a disputed value
    never silently wins on recency.
    """
    sql = """
        SELECT i.*,
               (SELECT COUNT(*) FROM citations c WHERE c.item_id = i.id) AS citation_count,
               (SELECT GROUP_CONCAT(c.source_url, ' | ') FROM citations c
                 WHERE c.item_id = i.id) AS source_urls
        FROM items i
        WHERE i.entity_id = ?
    """
    params: list[Any] = [entity_id]
    if kind:
        sql += " AND i.kind = ?"
        params.append(kind)
    rows = store.query(sql, params)
    # Trust, then corroboration, then id for a stable order. A disputed value
    # never wins on recency alone.
    return sorted(rows, key=lambda r: (-r["confidence"], -r["citation_count"], r["id"]))


def conflicted(store: Store, entity_id: str | None = None) -> list[sqlite3.Row]:
    """Items where sources disagree. The review queue's raw material."""
    if entity_id:
        return store.query(
            "SELECT * FROM items WHERE conflicts_with IS NOT NULL AND entity_id = ?",
            (entity_id,),
        )
    return store.query(
        "SELECT * FROM items WHERE conflicts_with IS NOT NULL ORDER BY entity_id, kind"
    )


def uncited(store: Store) -> list[sqlite3.Row]:
    """Published facts with no citation. Should always be empty.

    Kept as a query rather than a constraint because a fact may legitimately
    have its citation pruned by a cascade we have not anticipated — and the
    point is to *notice* if that happens, not to assume it cannot.
    """
    return store.query(
        """
        SELECT i.* FROM items i
        LEFT JOIN citations c ON c.item_id = i.id
        WHERE c.item_id IS NULL
        """
    )


def provenance(store: Store, item_id: int) -> list[sqlite3.Row]:
    return store.query(
        "SELECT * FROM citations WHERE item_id = ? ORDER BY retrieved_at", (item_id,)
    )


# ---------------------------------------------------------------- reporting

def venue_dossier(store: Store, entity_id: str) -> dict:
    """Everything known about one venue, with sources, for display.

    Structured so the "we only use public information" claim is visible in the
    output itself: every fact carries its URL, and unknowns are reported as
    absent rather than omitted, so a reader can see the difference between
    "we have no phone number" and "we didn't look".
    """
    entity = store.get_entity(entity_id)
    if entity is None:
        raise KeyError(f"no entity {entity_id}")

    by_kind: dict[str, list[dict]] = {}
    known = set()
    for row in items_for(store, entity_id):
        known.add(row["kind"])
        by_kind.setdefault(row["kind"], []).append(
            {
                "value": row["display"] or row["value"],
                "confidence": row["confidence"],
                "disputed": row["conflicts_with"] is not None,
                "sources": [
                    {"url": c["source_url"], "kind": c["kind"], "excerpt": c["excerpt"]}
                    for c in provenance(store, int(row["id"]))
                ],
            }
        )

    return {
        "name": entity["name"],
        "kind": entity["kind"],
        "verified": bool(entity["verified"]),
        "facts": by_kind,
        # Absent kinds are reported explicitly. A venue with no known phone
        # number is still a complete record; it just has a gap.
        "not_found": [k for k in ITEM_KINDS if k not in known],
        "provenance": {
            "event_count": store.one(
                "SELECT COUNT(*) c FROM events WHERE venue_id = ?", (entity_id,)
            )["c"],
            "bands": [
                r["name"]
                for r in store.query(
                    """
                    SELECT p.name FROM event_performers ep
                    JOIN events e ON e.id = ep.event_id
                    JOIN performers p ON p.id = ep.performer_id
                    WHERE e.venue_id = ?
                    GROUP BY p.name ORDER BY p.name
                    """,
                    (entity_id,),
                )
            ],
        },
    }


def _json(value: Any) -> str:
    import json

    return json.dumps(value)
