---
name: towncrier-event-discovery
description: Towncrier local event discovery, the downtown night sheet, and the agent write path. Rules and model.
---

# towncrier

Canonical repo: `/opt/shadenet/towncrier/`. Continuous discovery of
live music and local events for one town (Metropolis, CA, but the tree
is pointable). The night sheet is the public surface. Part of Derivee.
Personal tool, not a product.

Read `README.md` in that repo before changing the model or the sheet.

## The tree

Modelled as an oak, and the metaphor is load-bearing:

    Metropolis        trunk      (entity kind=city)
     |- The Royal     branch    (kind=venue, role=host)
     |   |- Foo       leaf      (kind=band)
     |   `- Show      acorn     (an *event* — not an entity)
     `- Gator Events  leaf      (kind=promoter)

Events are acorns hanging off branches, never off the trunk. Promoters are
leaves linked to venues via `entity_links` (rel='books') because "they don't
book their own shows" is a many-to-many edge, not a venue attribute.

## The two rules this project commits to

1. **A fact is publishable only if a public source backs it.**
   `entities.add_item` raises `UncitedFact` when there is no `source_url` and
   the caller has not declared the input `manual`. There is no code path that
   produces an uncited fact. A missing phone number does NOT disqualify a
   venue — the venue is the record, the phone number is one *item* that may
   or may not exist.

2. **Conflicting information is preserved, never resolved.** Two sources
   stating different values for one (entity, kind) produce two rows, linked
   via `conflicts_with`. Nothing is overwritten, ranked, or averaged. One
   value seen by many sources is *corroboration*, not conflict — the UNIQUE
   constraint collapses those to one row.

Both are enforced in code and tested, not just documented.

## No outbound contact

Never emails, texts, or messages venues, bands, or promoters. Cold contact
is off the table. A login wall on Facebook, Instagram, or X yields zero
events, not a guessed show. Only ingest a social event when a public page
itself lists a schema.org Event with a name and a start.

## Where the work lives

    towncrier/schema.sql     tree, items, citations, listings, events
    towncrier/store.py       sqlite wrapper
    towncrier/entities.py    the tree and the two rules
    towncrier/facts.py       cited enrichment from a venue's own pages
    towncrier/discover.py    OpenStreetMap Overpass, not Google Places
    towncrier/normalize.py   titles, dates, times, DST, performers
    towncrier/resolve.py     cluster listings into events
    nightcal/fill.py         downtown rooms, the public calendar, social pages
    nightcal/agent_events.py agent write path: add, correct, take down
    nightcal/surface.py      A2UI v0.9 sheet
    nightcal/server.py       HTTP server
    nightcal/static/         the page

Google Places is not a source. The Maps Platform terms forbid storing
Places content as a system of record. OpenStreetMap is the gazetteer.
ODbL attribution stays on the sheet.

## Agent writes

`POST /api/events` with a public `sourceUrl`, a title, and `startsAt`.
A correction is a new listing beside the old one. `DELETE /api/events/{id}`
records a takedown and leaves the listing row. Do not delete cited rows.
Do not wipe votes. Votes are samples keyed by listing URL.

## The sheet

Downtown only: Railroad Square through Courthouse Square to Main Street Tavern.
An open day uses four axes: hour across, one lane per show down, sample
tally toward the reader, duration as the wire. Kind is not an axis.
Do not invent shows. Do not run `fill()` unless the operator asked for
a refresh. Refresh re-reads the public calendar and OpenStreetMap.

## Testing

```bash
cd /opt/shadenet/towncrier
python3 tests/test_entities.py
python3 tests/test_normalize.py
python3 tests/test_resolve.py
python3 tests/test_discover.py
python3 tests/test_nightcal.py
```

## Hard-won constraints

- **DST is per-date.** `zoneinfo` in `normalize.to_utc`, never a fixed
  offset. US DST 2026 starts Mar 8, ends Nov 1, so a March 14 show is PDT
  (-7) and lands at 03:00Z while a December one is PST (-8) and 04:00Z.
- **`citations` is keyed (item_id, source_id)**, not item_id alone. A
  single-column key with INSERT OR REPLACE silently let a second source
  overwrite the first, destroying provenance.
- **`needs_review` must be computed for new events too.** Computing it only
  in the update branch let a freshly-inserted event keep the column default
  and bypass the whole policy.
- **Count cancellation sources, not `source_count`.** A show on a venue site
  *and* a ticketing site has source_count=2 even when only the venue
  cancelled, so a calendar rotation would publish as a real cancellation.
- **Don't trust search results for API status.** Vendor content farms still
  cite the dead Instagram Basic Display API. Check the platform's own docs.
- **Prefer the graveyard over rm.** `.graveyard/` keeps the misnamed
  calendar. Do not delete cited listings or venue rows.

See [[no-permanent-deletion]] before removing anything.
