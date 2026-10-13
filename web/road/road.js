// NightCal — The Road (prototype)
//
// The road is anchored at today. The foreground ("front panel") shows one day
// up close — today by default; click any date down the road to bring that
// day's shows to the front. The detail panel (front-left) shows whatever sign
// you hover or tap.
//
// One formula drives the perspective: p(d) = 1 / (1 + d / K), where d is how
// many rows a band is above the ground line. Road width, band height and sign
// scale all follow p(d), so the road's edges stay straight lines into the
// vanishing point and every band has the same *natural* width (Wb).
//
// Rules for billboards:
//   - A sign never leaves its own day's space (bands and lanes clip).
//   - Sign size is relative to the other events on THAT day (see signScale).
//   - Every date line shows its total count, and hidden events always get a
//     visible "+N more" button that brings the day to the front.

import { loadCalendar } from "../js/data/calendar.js";
import { eventCard } from "../components/event-card/event-card.js";
import { kindGlyph } from "../components/kind-tag/kind-tag.js";

// ---- Tunables --------------------------------------------------------------
const K = 1.6;            // larger = gentler perspective, more legible rows
const SINGLE_ROWS = 2;    // nearest rows hold one day; further rows hold two (lane split)
const MIN_SCALE = 0.12;   // stop drawing bands this close to the horizon
const MAX_GROW = 2.2;     // safety cap on billboard growth, whatever signScale returns
// Size of a standard (no-interest) sign; 1 = the original prototype size.
// Try others live with ?base=2.5 etc.
const SIGN_BASE = Math.min(6, Math.max(0.5, Number(new URLSearchParams(location.search).get("base")) || 4));
const POSTS = { full: 14 * SIGN_BASE, title: 8 * SIGN_BASE, dot: 0 };   // post height under each board
const SIGN = {            // natural (unscaled) billboard sizes per level of detail
  full: { w: 200 * SIGN_BASE, h: 96 * SIGN_BASE },
  title: { w: 150 * SIGN_BASE, h: 54 * SIGN_BASE },
  dot: { w: 30 * SIGN_BASE, h: 30 * SIGN_BASE },
};

const params = new URLSearchParams(location.search);
const DEMO = params.has("demo");
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
const SVG_NS = "http://www.w3.org/2000/svg";

const p = d => 1 / (1 + d / K);

/**
 * How big a billboard is, relative to the standard sign. Continuous (every
 * +1 or -1 moves it a little), relative to the event's own day, and damped on
 * days that are quiet compared with the calendar as a whole.
 *
 *   share = this event's bodies / all bodies that day     (its slice of the day)
 *   heat  = that day's bodies / a typical day's bodies    (how busy the day is), capped at 1
 *   size  = 1 + (MAX_GROW - 1) * sqrt(share * heat)
 *
 * sqrt makes early +1s visible; heat stops a lone +1 on a dead Tuesday from
 * producing a giant billboard. `bodies` is the net tally (+1s minus -1s).
 *
 * @param {number} bodies  net intended attendance for this event
 * @param {{dayTotal: number, typicalDay: number}} ctx
 * @returns {number} 1 for an event nobody has marked yet; up to MAX_GROW
 */
export function signScale(bodies, { dayTotal, typicalDay }) {
  if (bodies <= 0 || dayTotal <= 0) return 1;
  const share = bodies / dayTotal;
  const heat = Math.min(1, dayTotal / Math.max(1, typicalDay));
  return 1 + (MAX_GROW - 1) * Math.sqrt(share * heat);
}

// ---- State -------------------------------------------------------------------
const state = {
  model: null,
  dates: [],          // continuous list of ISO dates from today to the last listed date
  byDate: new Map(),  // date -> [event] after filters
  selected: null,     // date shown in the front panel (defaults to today)
  dayTotals: new Map(), // date -> net bodies that day (after filters)
  typicalDay: 0,      // average bodies per day, over days that have any
  pinned: null,       // event id pinned in the detail panel
  filters: { kinds: new Set(), free: false, hideCancelled: false },
};

const $ = id => document.getElementById(id);
const els = {
  road: $("road"), surface: $("road-surface"), rows: $("road-rows"),
  groundLabel: $("road-ground-label"), groundCount: $("road-ground-count"),
  today: $("road-today"), detail: $("road-detail"), back: $("road-back"), sky: $("road-sky"),
  kinds: $("road-kinds"), filters: $("road-filters"), source: $("road-source"),
};

const el = (tag, className, text) => {
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (text != null) n.textContent = text;
  return n;
};

// ---- Dates -------------------------------------------------------------------
const toUTC = iso => new Date(`${iso}T00:00:00Z`);
const addDays = (iso, n) => {
  const d = toUTC(iso); d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
};
const fmtLong = new Intl.DateTimeFormat("en-US", { weekday: "long", month: "long", day: "numeric", timeZone: "UTC" });
const fmtShort = new Intl.DateTimeFormat("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" });

function dayLabel(iso, { short = false } = {}) {
  const today = state.model.today;
  const f = short ? fmtShort : fmtLong;
  if (iso === today) return `Today · ${f.format(toUTC(iso))}`;
  if (iso === addDays(today, 1)) return `Tomorrow · ${f.format(toUTC(iso))}`;
  return f.format(toUTC(iso));
}

const countLabel = n => (n === 1 ? "1 show" : `${n} shows`);

// ---- Event facts the shared model doesn't carry ----------------------------
// normalize() drops status and price, so read them from the raw listing.
function enrich(model) {
  const raw = new Map((model.raw.events || []).map(e => [e.id, e]));
  for (const e of model.events) {
    const r = raw.get(e.id) || {};
    e.cancelled = /cancel/i.test(r.status || "") || r.eventStatus === "EventCancelled";
    e.category = (r.categories || []).find(c => c && c !== e.venueName) || "";
    e.free = r.isFree === true || r.isAccessibleForFree === true || r.price === 0
      || /^\s*free\s*$/i.test(String(r.price ?? "")) || /\bfree\b/i.test(String(r.priceLabel ?? ""));
    if (DEMO) demoize(e);
  }
}

// ?demo=1 — deterministic fake interest / cancellations / free events so every
// visual state can be seen before the real data exists.
function demoize(e) {
  let h = 0;
  for (const c of e.id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  e.bodies = h % 3 === 0 ? (h >>> 3) % 60 : 0;
  e.cancelled = h % 17 === 0;
  e.free = h % 4 === 1;
}

// ---- Filtering ---------------------------------------------------------------
function applyFilters() {
  const { kinds, free, hideCancelled } = state.filters;
  state.byDate = new Map();
  state.dayTotals = new Map();
  for (const e of state.model.events) {
    if (kinds.size && !kinds.has(e.kind)) continue;
    if (free && !e.free) continue;
    if (hideCancelled && e.cancelled) continue;
    if (!state.byDate.has(e.date)) state.byDate.set(e.date, []);
    state.byDate.get(e.date).push(e);
    state.dayTotals.set(e.date, (state.dayTotals.get(e.date) || 0) + Math.max(0, e.bodies || 0));
  }
  const busy = [...state.dayTotals.values()].filter(Boolean);
  state.typicalDay = busy.length ? busy.reduce((a, b) => a + b, 0) / busy.length : 0;
}

function growOf(e) {
  const g = Number(signScale(Math.max(0, e.bodies || 0), {
    dayTotal: state.dayTotals.get(e.date) || 0, typicalDay: state.typicalDay,
  }));
  return Number.isFinite(g) ? Math.min(MAX_GROW, Math.max(1, g)) : 1;
}

// ---- Signs ------------------------------------------------------------------
function signFor(e, lod, grow) {
  const btn = el("button", "road-sign");
  btn.type = "button";
  Object.assign(btn.dataset, { id: e.id, lod, tone: e.tone, shape: e.glyph });
  btn.classList.toggle("is-cancelled", !!e.cancelled);
  btn.classList.toggle("is-free", !!e.free);
  btn.classList.toggle("is-pinned", state.pinned === e.id);
  btn.style.setProperty("--grow", grow.toFixed(3));
  btn.setAttribute("aria-pressed", String(state.pinned === e.id));
  btn.setAttribute("aria-label", [
    e.title, e.kindLabel, e.timeDisplay, e.venueName,
    e.bodies ? `${e.bodies} going` : "",
    e.free ? "free" : "", e.cancelled ? "cancelled" : "",
  ].filter(Boolean).join(", "));

  // More interest = bigger sign = more room, so bigger signs say more:
  //   tier 1: title · start · venue · lineup (or kind)
  //   tier 2: + full time range, venue on its own line
  //   tier 3: + category tag
  const tier = lod !== "full" ? 0 : grow >= 1.7 ? 3 : grow >= 1.3 ? 2 : 1;
  btn.dataset.tier = String(tier);
  const board = el("span", "road-sign__board");
  board.append(kindGlyph(e.kind));
  if (lod !== "dot") board.append(el("span", "road-sign__title", e.title));
  if (lod === "title" && e.start) board.append(el("span", "road-sign__meta", e.start));
  if (lod === "full") {
    if (tier >= 2) {
      board.append(el("span", "road-sign__meta", e.timeDisplay || e.start));
      if (e.venueName) board.append(el("span", "road-sign__meta", e.venueName));
    } else {
      board.append(el("span", "road-sign__meta", [e.start, e.venueName].filter(Boolean).join(" · ")));
    }
    // Lineup only when it adds something the title doesn't already say
    const norm = t => t.toLowerCase().replace(/[^a-z0-9]+/g, "");
    const lineup = e.performers.filter(n => !norm(e.title).includes(norm(n)) && !norm(n).includes(norm(e.title))).slice(0, 3).join(", ");
    board.append(el("span", "road-sign__extra", lineup || e.kindLabel));
    if (tier >= 3 && e.category) board.append(el("span", "road-sign__tag", e.category));
  }
  if (e.cancelled && lod !== "dot") board.append(el("span", "road-sign__flag", "Cancelled"));
  btn.append(board);
  if (e.free && lod !== "dot") btn.append(el("span", "road-sign__free", "Free"));
  if (e.bodies && lod === "full") btn.append(el("span", "road-sign__bodies", `+${e.bodies}`));
  return btn;
}

/**
 * Fill one day's lane (natural size w×h). Most-attended first — they earn the
 * space — then shown in start-time order. Nothing ever leaves the lane.
 *
 * Quiet day: every show stands on posts as a billboard.
 * Busy day (more than fits): the lane switches to floating cards, and whatever
 * doesn't fit collapses into one stack — a visible pile with the hidden shows'
 * kind colours and a count. Clicking the stack brings the day to the front.
 */
function fillLane(lane, date, events, w, h, lod, { all = false } = {}) {
  lane.replaceChildren();
  lane.dataset.lod = lod;
  const sorted = [...events].sort((a, b) => (b.bodies || 0) - (a.bodies || 0) || a.minutes - b.minutes);
  const { w: sw, h: sh } = SIGN[lod];
  const gap = 10 * Math.min(2, SIGN_BASE), top = 6;

  // Simulate the flex-wrap. `extra` is a trailing item (the stack) that must also fit.
  const fits = (list, limit, posts, extra) => {
    let x = 0, y = top, rowH = 0;
    const items = list.map(e => { const g = growOf(e); return [Math.min(sw * g, w), sh * g + posts]; });
    if (extra) items.push(extra);
    for (const [ew, eh] of items) {
      if (x > 0 && x + ew > w) { y += rowH + gap; x = 0; rowH = 0; }
      if (y + eh > limit) return false;
      x += ew + gap;
      rowH = Math.max(rowH, eh);
    }
    return true;
  };
  const prefix = (limit, posts, extra) => {
    let n = 0;
    while (n < sorted.length && fits(sorted.slice(0, n + 1), limit, posts, extra)) n++;
    return sorted.slice(0, n);
  };

  let shown = all ? sorted : prefix(h, POSTS[lod]);
  const busy = !all && shown.length < sorted.length;
  if (busy && lod !== "dot") {
    // Floating cards (no posts) plus room for the stack at the end.
    shown = prefix(h, 0, [sw, sh + STACK_DEPTH * stackStep()]);
  } else if (busy) {
    shown = prefix(h, 0, [sw, sh]);            // far away: the stack is a single "+N" dot
  }
  lane.classList.toggle("is-busy", busy);

  shown.sort((a, b) => a.minutes - b.minutes);
  const signs = el("div", "road-lane__signs");
  for (const e of shown) signs.append(signFor(e, lod, growOf(e)));
  const rest = sorted.filter(e => !shown.includes(e));
  if (rest.length) {
    // If even the stack can't fit this lane, it becomes a "+N" dot sized to the lane.
    const stackH = lod === "dot" ? sh : sh + Math.min(STACK_DEPTH, rest.length - 1) * stackStep();
    const tooBig = !shown.length && (stackH + top > h || sw > w);
    signs.append(stackFor(date, rest, tooBig ? "dot" : lod, tooBig ? Math.max(8, Math.min(h - top, w)) : null));
  }
  lane.append(signs);
  if (!events.length && lod !== "dot") lane.append(el("p", "road-lane__quiet", "Nothing listed"));
}

const DATE_H = 36;                             // natural height of a day's date line
const STACK_DEPTH = 3;                         // ghost cards drawn behind the top one
const stackStep = () => 5 * SIGN_BASE;         // offset between layers (natural px)

// The pile of shows that didn't fit: layered cards, hidden kinds, and a count.
function stackFor(date, rest, lod, fitPx = null) {
  const n = rest.length;
  const layers = lod === "dot" ? 0 : Math.min(STACK_DEPTH, n - 1);
  const btn = el("button", "road-stack");
  btn.type = "button";
  btn.dataset.date = date;
  btn.dataset.lod = lod;
  btn.style.setProperty("--layers", String(layers));
  btn.setAttribute("aria-label", `${n} more ${n === 1 ? "show" : "shows"} on ${dayLabel(date)} — bring this day to the front`);
  for (let i = layers; i >= 1; i--) {
    const ghost = el("span", "road-stack__layer");
    ghost.style.setProperty("--i", String(i));
    ghost.dataset.tone = rest[i].tone;
    btn.append(ghost);
  }
  const top = el("span", "road-stack__top");
  top.dataset.tone = rest[0].tone;
  if (lod === "dot") {
    top.textContent = `+${n}`;
  } else {
    top.append(el("span", "road-stack__count", `+${n}`));
    const kinds = el("span", "road-stack__kinds");
    for (const e of rest.slice(0, 8)) kinds.append(kindGlyph(e.kind));
    top.append(kinds);
    if (lod === "full") top.append(el("span", "road-stack__hint", "more shows ›"));
  }
  btn.append(top);
  if (fitPx) {
    btn.style.width = btn.style.height = `${fitPx}px`;
    top.style.height = `${fitPx}px`;
    btn.style.fontSize = `${Math.max(6, fitPx * 0.45)}px`;
  }
  return btn;
}

// ---- Layout -----------------------------------------------------------------
function geometry() {
  const W = els.road.clientWidth, H = els.road.clientHeight;
  const portrait = H > W;
  const horizonY = H * 0.05;
  const groundY = H * (portrait ? 0.58 : 0.64);
  const G = groundY - horizonY;
  const Wb = Math.min(W * (portrait ? 0.98 : 0.86), G * 2.6);
  return { W, H, portrait, horizonY, groundY, G, Wb, yAt: d => horizonY + G * p(d) };
}

function svg(tag, className, attrs) {
  const n = document.createElementNS(SVG_NS, tag);
  n.setAttribute("class", className);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
  return n;
}

function drawSurface(g) {
  const { W, H, horizonY, groundY, G, Wb } = g;
  const cx = W / 2;
  // Road edges are straight lines through the vanishing point, extended to the bottom.
  const halfAt = y => (Wb / 2) * (y - horizonY) / G;
  els.surface.setAttribute("viewBox", `0 0 ${W} ${H}`);
  els.surface.replaceChildren(
    svg("polygon", "road__asphalt", { points: `${cx},${horizonY} ${cx + halfAt(H)},${H} ${cx - halfAt(H)},${H}` }),
    svg("line", "road__centre", { x1: cx, y1: horizonY, x2: cx, y2: H }),
    svg("line", "road__groundline", { x1: cx - halfAt(groundY), y1: groundY, x2: cx + halfAt(groundY), y2: groundY }),
  );
}

const bands = new Map(); // date -> band element (kept across renders)

function bandFor(date) {
  let band = bands.get(date);
  if (band) return band;
  band = el("section", "road-band");
  band.dataset.date = date;
  const line = el("h2", "road__line");
  const pick = el("button", "road__date");
  pick.type = "button";
  pick.dataset.date = date;
  pick.append(el("span", "road__date-label"), el("span", "road__date-count"));
  line.append(pick);
  band.append(el("div", "road__lane"), line);
  els.rows.append(band);
  bands.set(date, band);
  return band;
}

function render() {
  if (!state.model) return;
  const g = geometry();
  els.road.classList.toggle("is-portrait", g.portrait);
  els.road.style.setProperty("--ground-y", `${g.groundY}px`);
  drawSurface(g);
  placeSky(g);

  // Front panel: the selected day, every show, scrollable.
  const today = state.model.today;
  const sel = state.selected;
  const selEvents = state.byDate.get(sel) || [];
  els.groundLabel.textContent = dayLabel(sel);
  els.groundCount.textContent = countLabel(selEvents.length);
  els.back.hidden = sel === today;
  const groundH = g.H - g.groundY - 56;
  const laneW = g.portrait ? g.W - 24 : g.W / 2 - 48;
  fillLane(els.today, sel, selEvents, laneW, groundH, "full", { all: true });

  // The road always starts at tomorrow; the selected day is highlighted on it.
  const seen = new Set();
  let idx = 1;
  for (let r = 0; idx < state.dates.length; r++) {
    const s = p(r);
    if (s < MIN_SCALE) break;
    const days = r < SINGLE_ROWS ? [state.dates[idx]] : [state.dates[idx], state.dates[idx + 1]].filter(Boolean);
    idx += days.length;
    const yBottom = g.yAt(r), yTop = g.yAt(r + 1);
    const naturalH = (yBottom - yTop) / s;
    const clear = r === 0 ? 26 / s : 0;            // row 0's date must clear the ground label
    const header = DATE_H + clear;
    const lod = naturalH - header >= SIGN.full.h + POSTS.full + 10 ? "full"
      : naturalH - header >= SIGN.title.h + POSTS.title + 6 ? "title" : "dot";
    // Road width at this band's top edge, relative to its bottom edge: the date
    // line and the signs are inset so they end at the road's edges.
    const inset = (g.Wb * (1 - p(r + 1) / s)) / 2;
    days.forEach((date, i) => {
      const naturalW = days.length === 1 ? g.Wb : g.Wb / 2;
      const insetL = days.length === 2 && i === 1 ? 0 : inset;
      const insetR = days.length === 2 && i === 0 ? 0 : inset;
      const x = g.W / 2 - (g.Wb * s) / 2 + (i * g.Wb * s) / 2;
      const band = bandFor(date);
      const evs = state.byDate.get(date) || [];
      seen.add(date);
      band.dataset.split = days.length === 2 ? (i === 0 ? "left" : "right") : "none";
      band.classList.toggle("is-selected", date === sel);
      band.style.width = `${naturalW}px`;
      band.style.height = `${naturalH}px`;
      band.style.transform = `translate(${x}px, ${yTop}px) scale(${s})`;
      band.style.zIndex = String(100 - r);
      band.style.setProperty("--clear", `${clear}px`);
      band.style.setProperty("--inset-l", `${insetL}px`);
      band.style.setProperty("--inset-r", `${insetR}px`);
      band.querySelector(".road__date-label").textContent = dayLabel(date, { short: r >= SINGLE_ROWS });
      band.querySelector(".road__date-count").textContent = evs.length ? String(evs.length) : "";
      band.querySelector(".road__date").setAttribute("aria-label",
        `${dayLabel(date)}, ${countLabel(evs.length)} — bring this day to the front`);
      fillLane(band.querySelector(".road__lane"), date, evs, naturalW - 16 - insetL - insetR, naturalH - header, lod);
    });
  }
  for (const [date, band] of bands) {
    if (!seen.has(date)) { band.remove(); bands.delete(date); }
  }
  els.source.textContent = state.model.source === "live" && !DEMO ? ""
    : `Showing ${state.model.source} data${DEMO ? " with demo interest, cancellations and free events" : ""}`;
}

let frame = 0;
const schedule = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(render); };

// ---- Selecting a day ----------------------------------------------------------
function select(date) {
  if (!date || date === state.selected) return;
  state.selected = date;
  render();
  clearDetail();
  els.today.scrollTop = 0;
  els.groundLabel.closest("h1").focus({ preventScroll: true });
}

// ---- Sky ---------------------------------------------------------------------
// Everything left of the road and above the ground is sky; the selected event's
// image fills it, clipped to the road's left edge. (Portrait has no sky to speak of,
// so CSS hides it there and the viewer becomes a sheet.)
function placeSky(g) {
  els.road.classList.toggle("has-pick", !!state.pinned);
  const edgeAtGround = g.W / 2 - g.Wb / 2;
  els.sky.style.clipPath = `polygon(0 0, ${g.W / 2}px 0, ${g.W / 2}px ${g.horizonY}px, ${edgeAtGround}px ${g.groundY}px, 0 ${g.groundY}px)`;
  els.sky.style.height = `${g.groundY}px`;
  els.sky.style.width = `${g.W / 2}px`;
}

let skyFor = null;
function setSky(e) {
  const key = e ? `${e.id}|${e.image}` : "";
  if (key === skyFor) return;
  skyFor = key;
  const layer = el("div", "road__sky-layer");
  if (e?.image) {
    const img = el("img");
    img.src = e.image;
    img.alt = `Listing image for ${e.title}`;
    img.decoding = "async";
    layer.append(img);
  } else if (e) {
    // No listing image: the sky takes the kind's colour and shape instead
    layer.classList.add("is-placeholder");
    layer.dataset.tone = e.tone;
    layer.append(kindGlyph(e.kind));
  }
  const old = [...els.sky.children];
  els.sky.append(layer);
  requestAnimationFrame(() => requestAnimationFrame(() => layer.classList.add("is-in")));
  setTimeout(() => old.forEach(n => n.remove()), reducedMotion.matches ? 0 : 450);
}

// ---- Detail panel -----------------------------------------------------------
function showDetail(id) {
  const e = state.model.eventsById.get(id);
  if (!e) return;
  // The written part of the card (same container behaviour as the popup); the image goes to the sky.
  const frame = el("div", "road__viewer-card");
  frame.append(eventCard(e, { venue: state.model.venuesById.get(e.venueId), today: state.model.today, level: 2, showImage: false }));
  els.detail.replaceChildren(frame);
  setSky(e);
  els.detail.classList.toggle("is-cancelled", !!e.cancelled);
}

// The day's most-attended show (then earliest) — what the viewer shows by default.
function featured() {
  const evs = state.byDate.get(state.selected) || [];
  return [...evs].sort((a, b) => (b.bodies || 0) - (a.bodies || 0) || a.minutes - b.minutes)[0];
}

function clearDetail() {
  if (state.pinned) return showDetail(state.pinned);
  const top = featured();
  if (top) return showDetail(top.id);
  els.detail.classList.remove("is-cancelled");
  setSky(null);
  els.detail.replaceChildren(el("p", "road__hint", "Nothing listed for this day. Click a date down the road to bring it to the front."));
}

function pin(id) {
  state.pinned = state.pinned === id ? null : id;
  for (const s of document.querySelectorAll(".road-sign")) {
    const on = s.dataset.id === state.pinned;
    s.classList.toggle("is-pinned", on);
    s.setAttribute("aria-pressed", String(on));
  }
  if (state.pinned) showDetail(state.pinned); else clearDetail();
  els.road.classList.toggle("has-pick", !!state.pinned);
}

// ---- Input --------------------------------------------------------------------
const EVENT_TARGET = ".road-sign";
const DAY_TARGET = ".road__date, .road-stack";

function wireInput() {
  // Hover/focus previews an event; click/tap pins it. Dates and "+N more" open the day.
  els.road.addEventListener("pointerover", ev => {
    const s = ev.target.closest(EVENT_TARGET);
    if (s && ev.pointerType === "mouse") showDetail(s.dataset.id);
  });
  els.road.addEventListener("pointerout", ev => {
    const s = ev.target.closest(EVENT_TARGET);
    if (s && ev.pointerType === "mouse" && !s.contains(ev.relatedTarget)) clearDetail();
  });
  els.road.addEventListener("focusin", ev => {
    const s = ev.target.closest(EVENT_TARGET);
    if (s) showDetail(s.dataset.id);
  });
  els.road.addEventListener("click", ev => {
    const day = ev.target.closest(DAY_TARGET);
    if (day) return select(day.dataset.date);
    const s = ev.target.closest(EVENT_TARGET);
    if (s) pin(s.dataset.id);
  });
  els.back.addEventListener("click", () => select(state.model.today));

  // +1 / -1 in the detail card: resize that day's billboards right away.
  document.addEventListener("nc:bodies", ev => {
    const e = state.model.eventsById.get(ev.detail?.id);
    if (!e) return;
    e.bodies = Math.max(0, Number(ev.detail.bodies) || 0);
    applyFilters();
    schedule();
  });

  document.addEventListener("keydown", ev => {
    if (ev.target.closest("input, textarea, select")) return;
    if (ev.key === "Home") { ev.preventDefault(); select(state.model.today); }
    else if (ev.key === "Escape" && state.pinned) pin(state.pinned);
  });

  els.filters.addEventListener("change", () => {
    const f = new FormData(els.filters);
    state.filters.kinds = new Set(f.getAll("kind"));
    state.filters.free = f.has("free");
    state.filters.hideCancelled = f.has("hideCancelled");
    applyFilters();
    clearDetail();
    schedule();
  });

  new ResizeObserver(schedule).observe(els.road);
  reducedMotion.addEventListener?.("change", () => els.road.classList.toggle("is-still", reducedMotion.matches));
}

function buildKindFilters() {
  const kinds = [...new Set(state.model.events.map(e => e.kind))];
  for (const k of kinds) {
    const sample = state.model.events.find(e => e.kind === k);
    const label = el("label");
    label.dataset.tone = sample.tone;
    const input = Object.assign(document.createElement("input"), { type: "checkbox", name: "kind", value: k });
    label.append(input, kindGlyph(k), ` ${sample.kindLabel}`);
    els.kinds.append(label);
  }
}

// ---- Boot -------------------------------------------------------------------
(async function boot() {
  const model = await loadCalendar();
  enrich(model);
  state.model = model;
  state.selected = model.today;
  const last = model.events.reduce((m, e) => (e.date > m ? e.date : m), model.today);
  for (let d = model.today; d <= last; d = addDays(d, 1)) state.dates.push(d);
  els.road.classList.toggle("is-still", reducedMotion.matches);
  els.road.style.setProperty("--sign-base", String(SIGN_BASE));
  if (els.road.clientHeight > els.road.clientWidth) $("road-filters-wrap").open = false;
  buildKindFilters();
  applyFilters();
  wireInput();
  clearDetail();
  render();
})();
