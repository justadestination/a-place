# WorldSum street map and personal pages

Date: 2026-10-13
Status: approved in brainstorming, awaiting spec review

## Goal

Replace the Nuuksio forest sheet in `web/components/worldsum/` with a real
street map of a Finnish town standing in for downtown Santa Rosa. The map
shows, at a glance, what people have up (their flags) and how far away they
are, without showing where anyone actually is. Clicking a flag opens a small
personal page.

## Decisions

| Question | Decision |
| --- | --- |
| What hides people | Precision, not the map. A fixed Santa Rosa to Lahti mapping is reversible from two landmarks, so no one's position is ever drawn. |
| Main view | Rings around you: near, a walk, across town. Other flags sit at their real ring in a shuffled direction. |
| Venues | Real, public places drawn at their mapped spot. Anyone at a venue snaps to it, even alone. Flags are anonymous, so this shows that a flag is there, never who. |
| Crowds | Flags at one venue merge into one bigger flag with a head count and the intent icons of everything on offer. |
| Town | Lahti. Its market-square-to-station distance (803 m) is close to Courthouse Square to Railroad Square (762 m). The town is interchangeable; a hand-made map could replace the image later. |
| Map delivery | One static image, rendered once by a script and committed. No map server at runtime. |
| Flags as markers | Pennant plus intent icons ($ for sale, ⚒ work, ★ fun, … conversation, ? looking to buy). |
| Personal page | Small card skinned by the flag (field colour, charge, motto ribbon) with a few basics. Restyled by telling the Steward, using the existing order grammar. No friends list, no comments. |
| Human and Steward link | Not shown and not stored. All contact goes through the Steward and its relay. |
| Updates | A ping every 10 minutes and on opening the map. Live mode (about every 30 s) only on request; it switches off after 2 hours. |

## 1. The map image

- Script: `web/tools/build_worldsum_map.py`, run by hand, never at page load.
- Input: an OpenStreetMap extract of central Lahti (streets, water, rail),
  committed at `web/tools/data/lahti-osm.json`. ODbL; the map credits
  "© OpenStreetMap contributors".
- Output: `web/assets/worldsum/lahti.svg` in the site palette (parchment
  background, ink streets, water `#b9cfe0`), with no labels, and
  `web/js/data/worldsum-map.js` holding the image size, the Santa Rosa to
  Lahti transform, and every venue's position on the image.
- Transform: a similarity transform (scale, rotation, translation) taking
  Old Courthouse Square (38.44045, -122.71414) to Lahti Kauppatori, and
  Railroad Square (38.43794, -122.72228) to Lahti station. Measured: scale
  1.053, rotation 72°.
- Venues come from `towncrier/data/shadenet.db` `venues` (16 of 23 have
  coordinates). A venue without coordinates is left off the map and listed
  in the script's output.

## 2. Presence

### On the phone (`web/components/worldsum/presence.js`)

- Off by default. "Show my flag on the map" turns it on.
- Reads location with the browser Geolocation API.
- Within 60 m of a venue: reports `{venue_id}`. Otherwise it reports
  `{cell}`, a square of about 250 m on a fixed grid. The exact position never
  leaves the device.
- Schedule: on opening the map, then every 10 minutes. Live mode reports
  about every 30 s and turns itself off after 2 hours.
- A reported cell may change at most once per 5 minutes, even in live mode.

### On the server (`shadenet/serendipilyst/presence.py`)

- An in-memory table: flag id to `{cell | venue_id, expires}`. Entries expire
  20 minutes after the last ping. Nothing is written to disk and there is no
  history. A restart clears everyone.
- Only listed, active flags may report. The caller must be the flag's owner
  (signed-in Steward, as in `web.py`).
- `POST /api/flags/presence` with `{flag_id, cell | venue_id}` records the
  ping and returns the view for that caller:
  - `rings`: for each other present flag, `{flag_id, band}` where band is
    `near` (same or adjacent cell), `walk` (up to about 1 km), or `across`.
  - `venues`: for each venue with present flags, `{venue_id, count, intents,
    flags}`.
  - Never another flag's cell.
- `GET /api/flags/presence` returns the same view without a ping, for
  viewers who aren't sharing.

### Known limit

Someone who keeps moving can narrow a flag to roughly its 250 m cell by
watching which ring it falls into. Cells, the 5-minute cell-change cap, and
the 10-minute default bound this at block level. Flags are anonymous, so
the most it reveals is "this flag is around this block".

## 3. The map (`web/components/worldsum/worldsum.js`)

- Replaces the forest sheet and sample people with the Lahti image, venue
  marks, your position (drawn from the phone's own reading, never sent),
  rings, and flags.
- Ring placement: each flag gets a random bearing, fixed for the page visit,
  and a random distance inside its band.
- A flag at a venue is drawn on the venue. Two or more there become one
  pennant scaled by count, with a count badge and the union of their intent
  icons.
- Venue business flags (listed business nodes with an approved `venue_id`)
  are drawn on their venue.
- Clicking any flag opens its personal page. Clicking a crowd lists its
  flags.
- The flag workshop, the Steward order box, and the private room flow stay
  as they are.

## 4. Personal page (`web/components/flag-page/`)

- Opens from the map, or at `/market/flag/?id=<flag_id>`.
- Header: pennant, field colour, display name. Motto ribbon below.
- Body, each shown only when set: bio, good at, enjoys, won't be part of,
  marks, offer ("Up for grabs"), availability ("Around"), skill tags.
- "Tell their steward" opens the private room (existing `interest` flow).
- On your own page: the Steward box (same order grammar as the flag) plus
  plain fields for bio and availability.
- Data: `GET /api/flags/page?id=` returns the public fields of one listed or
  offered flag, using the same rules as `map_pins` (no owner, no address
  other than the relay).

## 5. Removals

- `personal_flags.linked_flag_id` and `_link_pair` in
  `shadenet/serendipilyst/personal.py`. The column stays in old databases
  but is no longer written or returned.
- The forest sheet data in `web/js/data/worldsum.js` (`PLACES`, `TRAILS`,
  `PEOPLE`, `ANCHORS`) and its tests. Flag `place_id` and the `PLACES` set in
  `flash.py` give way to presence. Listing still means "show my flag on the
  map".

## 6. Testing

- Python: cell and venue snapping, ping expiry, owner-only pings, the
  presence view never containing a cell, band thresholds, crowd counts and
  intent unions, page payload privacy.
- JS: ring placement stays inside its band, bearing is stable per visit,
  crowd merging.
- Browser (`web/tools/browser.mjs`): the map renders the image, venues,
  rings, and a crowd; clicking a flag opens its page; no console errors.

## Out of scope

- How release works in the Monero flow (waiting on the dead-drop design).
- Activation and the 21+ gate. Presence uses the current session sign-in
  until the Steward keypair lands.
