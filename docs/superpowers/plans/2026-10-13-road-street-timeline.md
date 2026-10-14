# Road continuous street timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace night-band rows on `/road/` with a continuous walk-up-the-street timeline where depth is clock time, night boundaries are curb lines, cards are large posters with text, the road is wider, and filters live in the foot.

**Architecture:** Pure layout in `web/road/layout.js` maps filtered listings to depth + optional night markers + lateral collision nudges. `web/road/road.js` renders markers and poster cards into the stage, jumps Further/Earlier by night marker, and mounts filters in `road__ground`. CSS grows poster faces and foot filter chrome. Article previews are out of scope.

**Tech Stack:** Vanilla ES modules, existing NightCal calendar model (`startsAt`, `minutes`, `date`, `image`), Playwright via `web/tools/browser.mjs`, node tests in `web/tests/test_road_layout.mjs`.

**Spec:** `docs/superpowers/specs/2026-10-13-road-street-timeline-design.md`

**Constraints:**
- Do not edit `web/css/nightcal.css` by hand.
- Do not invent showtimes; missing time → local noon placement + “time not listed” chip.
- Venue hues stay off pink/cyan (`venuePaint` / `VENUE_COLORS`).
- Do not stage `shadenet/data/*`, `docs/audit/report.json`, or run `web/tools/build_pages.py`.
- Do not push or deploy. Commit locally on this branch only.
- Bump `/road/` cache-bust query (and the `nc-road-bust` session token in `index.html` if the inline wipe script remains) whenever HTML/JS/CSS change.
- Live server may already be on `127.0.0.1:8765`; browser checks can use that or start a throwaway server on **8094+**.
- Git identity if needed: Shadenet Contributor `<contributor@shadenet.org>`.

---

## File map

| File | Role |
| --- | --- |
| `web/road/layout.js` | Add `listingInstant`, `timeDepth`, `timelinePlace`, widen default `road` fraction; keep `perspective`, `lodFor`, `signScale`, `venuePaint`. `bandFrames` may remain but road render stops using it. |
| `web/tests/test_road_layout.mjs` | TDD for the new pure functions + updated perspective defaults. |
| `web/road/road.js` | Timeline render, poster cards, night markers, foot filters, travel-by-marker. |
| `web/road/road.css` | Poster card face, marker line, foot filter layout, drop band-row dependence. |
| `web/road/index.html` | Move filters into foot; bump bust token. |

---

### Task 1: Pure time → depth + markers (TDD)

**Files:**
- Modify: `web/road/layout.js`
- Modify: `web/tests/test_road_layout.mjs`

- [ ] **Step 1: Write failing tests for instant + depth + timeline**

Append to `web/tests/test_road_layout.mjs` (import the new symbols):

```js
import {
  // existing imports…
  listingInstant,
  timeDepth,
  timelinePlace,
} from "../road/layout.js";

// --- continuous timeline ---
const noon = listingInstant({ date: "2026-10-17", minutes: 12 * 60 });
assert(noon.endsWith("12:00:00") || noon.includes("T12:00"), `noon default, got ${noon}`);
const stamped = listingInstant({ date: "2026-10-17", startsAt: "2026-10-17T19:30:00-07:00", minutes: 0 });
assert(stamped.includes("19:30") || Date.parse(stamped) === Date.parse("2026-10-17T19:30:00-07:00"), "startsAt wins");

const now = Date.parse("2026-10-17T18:00:00-07:00");
const dNear = timeDepth(Date.parse("2026-10-17T18:30:00-07:00"), now);
const dFar = timeDepth(Date.parse("2026-10-18T21:00:00-07:00"), now);
assert(dNear >= 0 && dFar > dNear, `near ${dNear} < far ${dFar}`);

const g = perspective(1440, 900);
assert(Math.abs(g.Wb / 1440 - 0.72) < 0.02, `wider desk road, Wb=${g.Wb}`);
const gp = perspective(390, 844);
assert(Math.abs(gp.Wb / 390 - 0.64) < 0.03, `wider phone road, Wb=${gp.Wb}`);

const placed = timelinePlace([
  { id: "a", title: "A", date: "2026-10-17", startsAt: "2026-10-17T19:00:00-07:00", minutes: 19 * 60, bodies: 2 },
  { id: "b", title: "B", date: "2026-10-17", startsAt: "2026-10-17T19:05:00-07:00", minutes: 19 * 60 + 5, bodies: 5 },
  { id: "c", title: "C", date: "2026-10-18", startsAt: "2026-10-18T20:00:00-07:00", minutes: 20 * 60, bodies: 1 },
], { now, geom: g, today: "2026-10-17" });
assert(placed.some(p => p.kind === "marker" && p.date === "2026-10-17"), "marker before first tonight show");
assert(placed.some(p => p.kind === "marker" && p.date === "2026-10-18"), "marker before next night");
const events = placed.filter(p => p.kind === "event");
assert(events[0].id === "a" || events[0].event.id === "a", "time order");
assert(events.length === 3, "three events");
const collide = events.filter(e => Math.abs((e.depth ?? e.d) - (events[0].depth ?? events[0].d)) < 0.05);
// a and b are 5 minutes apart — may share a slot; lateral nudge when same slot
const slot = timelinePlace([
  { id: "x", title: "X", date: "2026-10-17", startsAt: "2026-10-17T19:00:00-07:00", minutes: 1140, bodies: 1 },
  { id: "y", title: "Y", date: "2026-10-17", startsAt: "2026-10-17T19:00:00-07:00", minutes: 1140, bodies: 9 },
], { now, geom: g, today: "2026-10-17", collideMinutes: 15 });
const xs = slot.filter(p => p.kind === "event");
assert(xs.length === 2, "both same-minute shows kept");
assert(xs.some(p => (p.xNudge || 0) !== 0) || xs[0].x !== xs[1].x, "lateral nudge on collision");
```

Also update any existing asserts that expected road fraction `0.58` / `0.54` to `0.72` / `0.64`.

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd shadenet-a   # the repo root, or this worktree
node web/tests/test_road_layout.mjs
```

Expected: FAIL (missing exports / wrong road width).

- [ ] **Step 3: Implement in `layout.js`**

Add (names may match tests exactly):

```js
/** ISO-ish instant for sorting/placement. startsAt wins; else date + minutes; else local noon. */
export function listingInstant(event) {
  if (event?.startsAt) return String(event.startsAt);
  const date = event?.date;
  if (!date) return "";
  const minutes = Number.isFinite(Number(event?.minutes)) ? Number(event.minutes) : 12 * 60;
  const hh = String(Math.floor(minutes / 60) % 24).padStart(2, "0");
  const mm = String(minutes % 60).padStart(2, "0");
  return `${date}T${hh}:${mm}:00`;
}

/**
 * Depth from now. Minutes ahead map through a soft curve so the next hours
 * own the near road; later nights compress. Returns >= 0.
 */
export function timeDepth(startsMs, nowMs, { hourSpan = 18, k = 3.2 } = {}) {
  const rawMin = Math.max(0, (Number(startsMs) - Number(nowMs)) / 60000);
  const t = Math.min(1, rawMin / (hourSpan * 60));
  // Invert perspective-like: small t → small depth (near).
  const d = (k * t) / Math.max(1e-6, 1 - t + 1 / k);
  return d;
}

/**
 * Place markers + events for one camera. Each item:
 *   { kind:"marker", date, label?, depth, y, width }
 *   { kind:"event", event, depth, y, width, xNudge, lodHint? }
 * Empty today: if no event on `today`, still emit a today marker at depth 0.
 */
export function timelinePlace(events, { now, geom, today, collideMinutes = 12, maxLane = 3 } = {}) {
  const list = [...(events || [])].map(event => {
    const instant = listingInstant(event);
    const ms = Date.parse(instant) || Date.parse(`${event.date}T12:00:00`);
    return { event, instant, ms };
  }).filter(row => Number.isFinite(row.ms))
    .sort((a, b) => a.ms - b.ms || a.event.title.localeCompare(b.event.title));

  const out = [];
  let lastDate = null;
  const todayHas = list.some(row => row.event.date === today);
  if (today && !todayHas) {
    out.push({ kind: "marker", date: today, depth: 0, y: geom.yAt(0), width: geom.widthAt(0) });
    lastDate = today;
  }

  const groups = [];
  for (const row of list) {
    if (row.event.date !== lastDate) {
      const depth = Math.max(0, timeDepth(row.ms, now) - 0.08);
      out.push({ kind: "marker", date: row.event.date, depth, y: geom.yAt(depth), width: geom.widthAt(depth) });
      lastDate = row.event.date;
    }
    const depth = timeDepth(row.ms, now);
    groups.push({ ...row, depth });
  }

  // Collision buckets by rounded depth / time epsilon
  const epsMs = collideMinutes * 60000;
  let i = 0;
  while (i < groups.length) {
    let j = i + 1;
    while (j < groups.length && Math.abs(groups[j].ms - groups[i].ms) <= epsMs) j += 1;
    const bucket = groups.slice(i, j)
      .sort((a, b) => (b.event.bodies || 0) - (a.event.bodies || 0) || a.event.title.localeCompare(b.event.title));
    const shown = bucket.slice(0, maxLane);
    const rest = bucket.slice(maxLane);
    const n = shown.length;
    shown.forEach((row, idx) => {
      const xNudge = n === 1 ? 0 : (idx - (n - 1) / 2) * 0.22; // fraction of road half-width
      out.push({
        kind: "event",
        event: row.event,
        id: row.event.id,
        depth: row.depth,
        y: geom.yAt(row.depth),
        width: geom.widthAt(row.depth),
        xNudge,
        overflow: rest.length,
      });
    });
    i = j;
  }

  return out.sort((a, b) => a.depth - b.depth || (a.kind === "marker" ? -1 : 1));
}
```

Change default road fractions in `perspective()`:

```js
const fraction = road == null
  ? (portrait ? 0.64 : 0.72)
  : Math.max(0.18, Math.min(0.92, Number(road) || 0.46));
```

Tune `timeDepth` until the tests pass; keep the public signature stable.

- [ ] **Step 4: Run tests — expect PASS**

```bash
node web/tests/test_road_layout.mjs
```

Expected: `road layout checks passed`

- [ ] **Step 5: Commit**

```bash
git add web/road/layout.js web/tests/test_road_layout.mjs
git commit -m "feat(road): time-depth timeline placement helpers"
```

---

### Task 2: Move filters into the foot (markup + CSS)

**Files:**
- Modify: `web/road/index.html`
- Modify: `web/road/road.css`

- [ ] **Step 1: Move the filters `<details>` inside `road__ground`**

In `index.html`, cut `#road-filters-wrap` from after the ground section and place it inside `.road__travel` (end of that flex row) or as a sibling under `road__ground` after travel. Keep the same ids (`road-filters-wrap`, `road-filters`, `road-kinds`) so `road.js` element refs keep working.

Bump cache bust: replace the current `?v=…` on css/js and the inline `bust = "…"` / `nc-road-bust` token with a new token e.g. `timeline1`. Recompute the CSP `script-src` sha256 for the inline boot script if you change it (same method as existing street1 bust).

- [ ] **Step 2: Foot filter CSS**

In `road.css`:

- `.road__ground` becomes a column: date heading, travel row, optional open filter panel.
- `.road__travel` is flex wrap; Filter summary looks like the other travel controls.
- `[open]` panel: `position: absolute; bottom: 100%; left: 0; right: 0;` (or expand upward within ground) with `max-height: min(40vh, 16rem); overflow: auto;` so the road stays visible.
- Remove or neutralize old floating `.road__filters` stage positioning (top/right absolute on the stage).

- [ ] **Step 3: Smoke in browser (optional this task)**

Open `/road/?scope=all` — Filter control visible in the foot; opening it does not cover the whole stage.

- [ ] **Step 4: Commit**

```bash
git add web/road/index.html web/road/road.css
git commit -m "feat(road): move filters into the foot"
```

---

### Task 3: Render timeline + night markers + poster cards

**Files:**
- Modify: `web/road/road.js`
- Modify: `web/road/road.css`

- [ ] **Step 1: Replace band render with timeline place**

In `render()` (or equivalent):

1. `const geom = perspective(stageW, stageH);`
2. Collect filtered upcoming events (existing `passes` + date >= selected/today window). When `state.selected` is set via Further, treat that night’s first show as the near end: either filter `startsAt >= firstShowOf(selected)` or shift `now` to that marker’s instant — pick one and keep Further/Earlier consistent (spec: after jump, that night is the foot label and near end).
3. `const placed = timelinePlace(events, { now, geom, today: todayIso() });`
4. Replace `drawBands` with `drawTimeline(placed, geom)`:
   - Markers → `.road-marker` div (or svg line) with date label via existing `relative` / `bandName` helpers.
   - Events → `makeSign` positioned at `y`, centered with `translate(calc(-50% + xNudge * halfRoad), -100%)` (feet on the depth line).

Stop calling `bandFrames` from `road.js`.

- [ ] **Step 2: Enlarge poster cards in `makeSign`**

For `lod === "full"`:

- Size ~`min(220, max(160, widthAtDepth * 0.34))` square-ish card (cap by available width).
- Face structure:

```html
<button class="road-sign" data-lod="full">
  <span class="road-sign__edge"></span>
  <span class="road-sign__face">
    <img class="road-sign__img" alt="" />  <!-- if event.image -->
    <span class="road-sign__mark" data-shape="…"></span>
    <span class="road-sign__meta">
      <span class="road-sign__title">…</span>
      <span class="road-sign__when">7:30 pm</span> <!-- or Time not listed -->
    </span>
  </span>
</button>
```

- Keep venue CSS vars, entry `--stroke`, kind mark.
- `title` LOD: chip with title + when, no image.
- `dot` LOD: glyph only.
- LOD pick from on-screen card height / distance (reuse `lodFor` with the computed card side, or map depth thresholds: full if `p(d) > 0.55`, title if `> 0.28`, else dot — tune so nearest looks like a poster).

- [ ] **Step 3: CSS for posters + markers**

- `.road-sign[data-lod="full"]` — column face, image `object-fit: cover` top ~60%, meta below; kind mark corner.
- `.road-marker` — thin trapezoid/hairline across road width at that depth + centered label (text-shadow for night).
- Ensure `.road__rows` (or new `.road__timeline`) stacks markers/signs with pointer-events correct (signs auto, markers none except label button if clickable to select that night).

- [ ] **Step 4: Travel by night marker**

Update `neighbor(dir)` / Further / Earlier to move `state.selected` to the previous/next **date that has a marker** (listing dates), then re-render with that night at the near end.

- [ ] **Step 5: Commit**

```bash
git add web/road/road.js web/road/road.css web/road/index.html
git commit -m "feat(road): continuous timeline render with poster cards"
```

---

### Task 4: Browser verification + cache bust

**Files:**
- Possibly: `web/road/index.html` (bust token), screenshots under `/tmp/road-timeline/` (do not commit screenshots unless docs ask)

- [ ] **Step 1: Node tests still green**

```bash
node web/tests/test_road_layout.mjs
```

- [ ] **Step 2: Desk + phone screenshots**

Use `web/tools/browser.mjs` with `serviceWorkers: "block"`, viewports 1440×900 and 390×844:

1. `/road/?scope=all` — markers visible, cards have images/titles near camera, filters in foot.
2. Click Further until a busy night (e.g. 2026-10-17) is near — shows spaced by time, not one horizontal row.
3. Hover a sign — left sky poster + right facts still work.
4. Open Filter from the foot — panel usable.

Save under `/tmp/road-timeline/`.

- [ ] **Step 3: Fix anything broken; re-bust if HTML/JS/CSS changed**

- [ ] **Step 4: Final commit**

```bash
git add web/road/layout.js web/road/road.js web/road/road.css web/road/index.html web/tests/test_road_layout.mjs
git commit -m "feat(road): verify continuous street timeline"
```

Only stage the road files touched. Do not stage `shadenet/data/*`.

- [ ] **Step 5: Append completion record**

If the shared `hermes-completions.log` (outside the repo) is writable (chmod 644, append, chmod 444):

```text
DUAL_TASK_RECORD {"timestamp":"…","worker":"hermes","branch":"<this-branch>","commit":"<sha>","task":"road-street-timeline","title":"Continuous street timeline","status":"VERIFIED_SUCCESS","details":"…"}
```

---

## Spec coverage checklist

| Spec item | Task |
| --- | --- |
| Continuous time depth | Task 1–3 |
| Night curb markers | Task 1 + 3 |
| Poster cards + LOD | Task 3 |
| Wider road 0.72/0.64 | Task 1 |
| Filters in foot | Task 2 |
| Further/Earlier by night | Task 3 |
| Hover sky unchanged | Task 3–4 |
| Missing time → noon + chip | Task 1 + 3 |
| Collision nudge / +N | Task 1 + 3 |
| No articles | — |
| Tests + browser | Task 1 + 4 |

## Done when

- `node web/tests/test_road_layout.mjs` passes.
- Desk/phone screenshots show time-ordered depth, night lines, large near posters, foot filters.
- Commits exist on the worker branch; no push/deploy required.
