# NightCal road — continuous street timeline

Date: 2026-10-13  
Status: approved for planning  
Page: `web/road/` (layout.js, road.js, road.css, index.html)

## Goal

Make the road read as a walk up the street toward upcoming shows: depth is clock time, night boundaries are curb lines, cards are large enough to show a poster and a title, the road is wide enough to hold them, and filters live in the foot. Article previews stay out of this pass.

## Decisions (locked)

1. **Continuous timeline.** Each listing is its own depth from `startsAt` (falling back to `minutes` on the event’s `date`). Nearest = soonest from “now.” Night bands as equal-height rows go away.
2. **Night marker lines.** Before the first show of each night, draw a curb line across the road with a short date label (Tonight / Tomorrow / Fri 17). Walking forward, you cross the line into that night’s shows.
3. **Poster cards.** Near signs are large cards: image face, title, start time. Kind glyph is a small corner mark. Venue color frames the card. Entry price remains border weight. Attendance + distance still scale size. Mid depth → title chips; far → dots.
4. **Wider road.** Default road fraction rises to about **0.72** landscape / **0.64** portrait so more cards fit abreast when times collide.
5. **Filters in the foot.** Move the Filter control into `road__ground` beside travel (Earlier · date · Further · Week). The open panel sits in the foot, not as a floating stage overlay. Portrait keeps Filter collapsed by default.
6. **Travel.** Further / Earlier jump to the next / previous **night marker** (first show of that night). After a jump, that night’s date is the foot’s selected label and the near end of the visible window. Drag still scrubs along the road. Hover / pin keep left-sky poster + right-sky facts.
7. **Out of scope.** Latest-article previews, pink/cyan venue hues, hand-edits to `nightcal.css`, commit/deploy of the running UI until the user asks.

## Layout model

### Time → depth

- Build an ordered list of upcoming listings that pass the current filters, sorted by `startsAt` ascending (stable tie-break: title).
- Map each listing to a depth `d` in \([0, dMax]\) from a time delta `t = startsAt - now` (clamped). Use a smooth curve so the next few hours occupy most of the near road and later nights compress toward the horizon (same family as today’s `k` perspective, retuned for minutes instead of night index).
- Screen position still uses `perspective()`: `y = horizonY + G * p(d)`, `width = Wb * p(d)`. Street-level defaults stay (eye-height horizon, ground at stage floor).

### Night markers

- When the calendar date of listing `i` differs from listing `i-1` (or `i` is the first listing of a date after “now”), insert a **marker** at a depth just before that listing (small epsilon earlier than the first show).
- Marker renders as a trapezoid hairline + label; it is not hoverable as an event.
- Empty today: if nothing is listed tonight, keep a standing marker for today at the near end so the foot still has a place to stand.

### Collisions

- Two shows within a small time epsilon share depth; nudge them laterally (±x) inside the road width, priority by attendance then title.
- If more than ~3 share a slot, show the top by attendance and a `+N` chip for the rest (same overflow idea as today’s pack).

### Missing times

- No `startsAt` / `minutes`: place at local noon on `date`, show a “time not listed” chip on the card and in the sky fact panel. Do not invent a showtime beyond that default placement.

## Cards and LOD

| LOD | When | Face |
| --- | --- | --- |
| full | near, tall lane | image (cover), title (2 lines max), start time; kind mark; venue frame; entry stroke |
| title | mid | title + time on venue-colored chip; kind mark |
| dot | far / tiny | venue-colored glyph only |

- Image from the listing’s `image` when present; otherwise a venue-tinted blank with the kind mark.
- Sign scale ceiling stays Decision 005 (`SCALE_MAX` 1.75) with the day-share nudge.
- Near full cards target roughly **160–220px** on a desk stage (up from ~96–148), capped by road width at that depth.

## Chrome

### Foot

```
[ Earlier ] [ date ] [ Further N ] [ Week ]   [ Filter ▾ ]
Tonight · Fri 17 · 3 listed
```

- Filter `<details>` moves inside `road__ground`.
- Open filter panel expands upward from the foot (max-height capped so the road stays visible).
- Existing filter semantics unchanged: scope (nights / all), kinds, free, hide cancelled.

### Sky

- Unchanged for this pass: hover / pin → left bay poster, right fact panel.
- Idle left sky can stay empty (article stack deferred).

## Data and encoding (unchanged)

- Distance ≈ time (now continuous).
- Size ≈ attendance (`signScale` / billboardScale).
- Shape ≈ kind (corner mark on full cards; full shape on dots).
- Border ≈ entry weight.
- Color ≈ venue (`venuePaint`, no pink / no cyan).

## Files to touch

- `web/road/layout.js` — time→depth, marker insertion, collision nudge, wider default road fraction; keep pure and unit-tested.
- `web/road/road.js` — replace band-row render with listing+marker render; bigger card DOM; foot filter mount; travel-by-marker.
- `web/road/road.css` — wider road vars, poster card face, marker line, foot filter layout; remove band-row assumptions where obsolete.
- `web/road/index.html` — move filters markup into the foot; bump cache-bust token.
- `web/tests/test_road_layout.mjs` — depth ordering, markers between dates, noon default, collision nudge, wider defaults.
- `web/sw.js` — already network-first for `/road/`; bump bust token only if HTML/SW wipe needed.

## Testing

- Node: layout unit tests above.
- Browser (desk + phone): continuous depth for a busy night (e.g. 2026-10-17), marker lines labeled, near poster cards with titles, Further jumps night-to-night, filters usable from the foot, hover sky still works.
- Cache: reload with new `?v=` after HTML change; SW remains network-first for `/road/`.

## Risks

- Dense nights (10+ listings) can crowd the near road; lateral nudge + `+N` mitigate, but a future pass may need a “cluster” LOD.
- Listings with bad/missing `startsAt` cluster at noon; the chip makes that visible.
- Moving filters into the foot reduces stage height slightly; street-level `ground = stageH` already tracks the stage box.

## Non-goals

- Article / zine previews in the sky.
- Replacing the week calendar or today page.
- Changing steward vote API or tally curve formula.
- Production deploy.
