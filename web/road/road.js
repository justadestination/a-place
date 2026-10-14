// NightCal road. You stand at the near end and look toward the horizon.
// The night you are in is the closest row. Later listing nights recede.
// Sign size is attendance, shape is the kind, border thickness is the entry
// price, and color is the venue. Hover sends the picture to the left sky
// and the facts to the right sky. A click holds them there.

import { loadCalendar, KINDS } from "../js/data/calendar.js";
import { button } from "../components/button/button.js";
import { shareButton } from "../components/share-button/share-button.js";
import { isValidDate, label, relative } from "../js/data/dates.js";
import { shareUrl } from "../js/core/share.js";
import { isStewardActive, openStewardDrawer } from "../components/steward-drawer/steward-drawer.js";
import { reducedMotion } from "../js/core/theme.js";
import {
  SCALE_MAX,
  bandFrames,
  effectiveBodies,
  entryLabel,
  entryStroke,
  listingDates,
  lodFor,
  packSigns,
  perspective,
  signScale,
  posterFit,
  standAt,
  venuePaint,
} from "./layout.js?v=street1";

const SVG_NS = "http://www.w3.org/2000/svg";
const STEWARD_PAYLOAD = "shadenet_steward_payload";
const STEWARD_LOCAL = "shadenet_steward_local_id";

const $ = id => document.getElementById(id);
const els = {
  road: $("road"),
  stage: $("road-stage"),
  surface: $("road-surface"),
  rows: $("road-rows"),
  sky: $("road-sky"),
  info: $("road-info"),
  clear: $("road-clear"),
  heading: $("road-front-heading"),
  groundLabel: $("road-ground-label"),
  groundWhen: $("road-ground-when"),
  groundCount: $("road-ground-count"),
  earlier: $("road-earlier"),
  further: $("road-further"),
  remain: $("road-remain"),
  jump: $("road-jump"),
  week: $("road-week"),
  back: $("road-back"),
  filters: $("road-filters"),
  filtersWrap: $("road-filters-wrap"),
  kinds: $("road-kinds"),
  source: $("road-source"),
  status: $("road-status"),
};

const state = {
  model: null,
  byDate: new Map(),
  dates: [],
  selected: "",
  pinned: null,
  shownKey: null,
  skyId: null,
  scope: "nights",
  kinds: new Set(),
  free: false,
  hideCancelled: false,
  voted: new Set(),
  portrait: false,
  preview: null,
  kindKey: "",
  demo: false,
};

let suppressClick = false;
let lastWheel = 0;
let resizeTries = 0;

const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
};

const byId = id => state.model?.eventsById.get(id) || null;
const eventsOn = date => state.byDate.get(date) || [];
const todayIso = () => state.model.today;
const venueIds = () => (state.model?.venues || []).map(venue => venue.id);

function going(event) {
  return effectiveBodies(event, state.voted.has(event.id));
}

function passes(event) {
  if (!event || event.date < todayIso()) return false;
  if (state.scope !== "all" && !event.night) return false;
  if (state.kinds.size && !state.kinds.has(event.kind)) return false;
  if (state.free && !event.free) return false;
  if (state.hideCancelled && event.cancelled) return false;
  return true;
}

function countLabel(n) {
  const noun = state.scope === "all" ? "listing" : "show";
  return n === 1 ? `1 ${noun}` : `${n} ${noun}s`;
}

function recompute() {
  state.byDate = new Map();
  const visible = [];
  for (const event of state.model.events) {
    if (!passes(event)) continue;
    visible.push(event);
    if (!state.byDate.has(event.date)) state.byDate.set(event.date, []);
    state.byDate.get(event.date).push(event);
  }
  state.dates = listingDates(visible, todayIso());
}

function ranked(events) {
  const list = events || [];
  const bodies = list.map(going);
  const dayTotal = bodies.reduce((sum, n) => sum + n, 0);
  return list
    .map(event => ({
      event,
      bodies: going(event),
      scale: signScale(going(event), { dayTotal, count: list.length }),
    }))
    .sort((a, b) => b.bodies - a.bodies || a.event.minutes - b.event.minutes || a.event.title.localeCompare(b.event.title));
}

function readUrl() {
  const q = new URLSearchParams(location.search);
  state.demo = q.has("demo");
  state.scope = q.get("scope") === "all" ? "all" : "nights";
  state.kinds = new Set(
    (q.get("kind") || "").split(",").map(part => part.trim()).filter(kind => KINDS[kind]),
  );
  state.free = q.get("free") === "1";
  state.hideCancelled = q.get("cancelled") === "hide";
  const date = q.get("date");
  state.pendingDate = isValidDate(date) ? date : "";
  state.pendingEvent = q.get("event") || "";
}

function applyDemo(events) {
  if (!state.demo) return;
  for (const event of events) {
    let hash = 0;
    for (const char of String(event.id)) hash = (hash * 33 + char.charCodeAt(0)) >>> 0;
    event.bodies = hash % 5 === 0 ? hash % 80 : hash % 7 === 0 ? 1 : 0;
  }
}

function loadVotes() {
  state.voted = new Set();
  for (const event of state.model.events) {
    try {
      if (localStorage.getItem(`nc_tally_${event.id}`) === "1") state.voted.add(event.id);
    } catch { /* private mode */ }
  }
}

function bootSelection() {
  const event = state.pendingEvent && state.model.events.find(item => item.id === state.pendingEvent && passes(item));
  if (event) {
    state.pinned = event.id;
    state.selected = event.date;
    return;
  }
  state.pinned = null;
  if (state.pendingDate && state.pendingDate >= todayIso()) state.selected = state.pendingDate;
  else state.selected = todayIso();
}

function neighbor(dir) {
  const dates = state.dates;
  const selected = state.selected;
  const index = dates.indexOf(selected);
  if (dir > 0) {
    if (index >= 0) return dates[index + 1] || "";
    return dates.find(date => date > selected) || "";
  }
  if (index > 0) return dates[index - 1];
  if (index === 0) return "";
  const prev = [...dates].reverse().find(date => date < selected);
  if (prev) return prev;
  return selected !== todayIso() ? todayIso() : "";
}

function announce(text) {
  els.status.textContent = "";
  requestAnimationFrame(() => { els.status.textContent = text; });
}

function syncUrl() {
  const q = new URLSearchParams();
  if (state.selected && state.selected !== todayIso()) q.set("date", state.selected);
  if (state.pinned) q.set("event", state.pinned);
  if (state.scope === "all") q.set("scope", "all");
  if (state.kinds.size) q.set("kind", [...state.kinds].join(","));
  if (state.free) q.set("free", "1");
  if (state.hideCancelled) q.set("cancelled", "hide");
  if (state.demo) q.set("demo", "1");
  const currentParams = new URLSearchParams(location.search);
  for (const key of ["scheme", "textScale", "density", "motion"]) {
    const value = currentParams.get(key);
    if (value) q.set(key, value);
  }
  const next = q.toString();
  const current = location.search.replace(/^\?/, "");
  if (next === current && (location.pathname === "/road" || location.pathname === "/road/")) return;
  history.replaceState({ road: true }, "", next ? `/road/?${next}` : "/road/");
}

function weekHref() {
  const q = new URLSearchParams();
  if (state.selected && state.selected !== todayIso()) q.set("date", state.selected);
  if (state.scope === "all") q.set("scope", "all");
  const search = q.toString();
  return search ? `/?${search}` : "/";
}

function skyEvent() {
  const pinned = state.pinned ? byId(state.pinned) : null;
  if (pinned && passes(pinned)) return pinned;
  const preview = state.preview ? byId(state.preview) : null;
  if (preview && passes(preview)) return preview;
  return null;
}

function paintFor(event) {
  return venuePaint(event?.venueId || "", venueIds());
}

function paintPicture(event) {
  els.sky.replaceChildren();
  els.sky.removeAttribute("data-wash");
  els.road.style.removeProperty("--sky-wash");
  if (!event) return;
  const bay = el("div", "road__sky-bay");
  if (event.image) {
    const img = document.createElement("img");
    img.className = "road__sky-img";
    img.alt = "";
    img.decoding = "async";
    img.dataset.fit = "cover";
    const applyFit = () => {
      if (img.naturalWidth && img.naturalHeight) {
        img.dataset.fit = posterFit(img.naturalWidth, img.naturalHeight);
      }
    };
    img.addEventListener("load", applyFit);
    img.src = event.image;
    if (img.complete) applyFit();
    bay.append(img);
    els.sky.append(bay);
    return;
  }
  const paint = paintFor(event);
  bay.dataset.wash = "1";
  els.road.style.setProperty("--sky-wash", paint.venue);
  els.sky.append(bay);
}

function dispatchBodies(node, id, bodies, direction) {
  node.dispatchEvent(new CustomEvent("nc:bodies", {
    bubbles: true,
    detail: { id, bodies, direction },
  }));
}

function tallyButtons(event) {
  const id = event.id;
  const voted = state.voted.has(id);
  const row = el("div", "road-info__tally");
  row.append(button({
    label: "+1",
    variant: voted ? "primary" : "ghost",
    attrs: {
      title: "Add +1 intended attendance (Steward required)",
      "aria-label": `Add 1 to attendance for ${event.title}`,
    },
    onClick: e => {
      e.preventDefault();
      e.stopPropagation();
      if (!isStewardActive()) {
        openStewardDrawer("Adding your intended attendance (+1) requires an active Personal Steward. Complete the quick 21+ verification to participate.");
        return;
      }
      if (state.voted.has(id)) return;
      try { localStorage.setItem(`nc_tally_${id}`, "1"); } catch { /* private mode */ }
      dispatchBodies(e.currentTarget, id, going(byId(id)) + 1, "+");
    },
  }), button({
    label: "−1",
    variant: "ghost",
    attrs: {
      title: "Retract intended attendance",
      "aria-label": `Retract attendance for ${event.title}`,
      disabled: voted ? null : "true",
    },
    onClick: e => {
      e.preventDefault();
      e.stopPropagation();
      if (!isStewardActive()) {
        openStewardDrawer("Modifying attendance tallies requires an active Personal Steward.");
        return;
      }
      if (!state.voted.has(id)) return;
      try { localStorage.removeItem(`nc_tally_${id}`); } catch { /* private mode */ }
      const item = byId(id);
      dispatchBodies(e.currentTarget, id, Math.max(0, (item ? going(item) : 1) - 1), "retract");
    },
  }));
  return row;
}

function paintInfo(event) {
  els.info.classList.toggle("is-held", !!(event && state.pinned === event.id));
  if (!event) {
    els.info.style.removeProperty("--info-venue");
    els.info.replaceChildren(el("p", "road__hint", "Hover a sign. Click it to keep it here."));
    return;
  }
  const paint = paintFor(event);
  els.info.style.setProperty("--info-venue", paint.venue);
  const when = [relative(event.date, todayIso()), event.timeDisplay || event.start].filter(Boolean).join(" · ");
  const where = el("p", "road-info__where");
  const swatch = el("span", "road-info__swatch");
  swatch.style.background = paint.venue;
  swatch.setAttribute("aria-hidden", "true");
  where.append(swatch, document.createTextNode(event.venueName || "Venue not listed"));

  const entry = entryLabel(event);
  const entryText = entry === "Free" || entry === "Entry not listed" ? entry : `Entry ${entry}`;
  const goingRow = el("p", "road-info__going");
  goingRow.append(document.createTextNode(`${going(event)} going`), tallyButtons(event));

  const actions = el("div", "road-info__actions");
  if (event.url) {
    actions.append(button({
      label: "Event page",
      variant: "primary",
      href: event.url,
      external: true,
    }));
  }
  const whenShare = [relative(event.date, todayIso()), event.timeDisplay || event.start].filter(Boolean).join(" ");
  actions.append(shareButton({
    title: event.title,
    text: `${event.title} — ${whenShare}${event.venueName ? `, ${event.venueName}` : ""}`,
    url: shareUrl(`/road/?date=${encodeURIComponent(event.date)}&event=${encodeURIComponent(event.id)}`),
  }));

  const panel = el("article", "road-info");
  panel.append(
    el("h2", "road-info__title", event.title),
    el("p", "road-info__when", when),
    where,
    el("p", "road-info__kind", event.kindLabel),
    el("p", "road-info__entry", entryText),
  );
  if (event.cancelled) panel.append(el("p", "road-info__cancelled", "Cancelled"));
  panel.append(goingRow, actions);
  els.info.replaceChildren(panel);
}

function paintSky() {
  const event = skyEvent();
  const id = event?.id || "";
  if (id !== state.skyId) {
    state.skyId = id;
    paintPicture(event);
  }
  const infoKey = event ? `${event.id}:${going(event)}:${state.voted.has(event.id) ? 1 : 0}:${state.pinned === event.id ? 1 : 0}` : "";
  if (infoKey !== state.shownKey) {
    state.shownKey = infoKey;
    paintInfo(event);
  }
}

function signLabel(event) {
  const entry = entryLabel(event);
  return [
    event.title,
    event.kindLabel,
    event.timeDisplay || event.start,
    event.venueName,
    `${going(event)} going`,
    entry,
    event.cancelled ? "cancelled" : "",
  ].filter(Boolean).join(", ");
}

function makeSign(item, lod) {
  const event = item.event;
  const paint = paintFor(event);
  const btn = el("button", "road-sign");
  btn.type = "button";
  btn.dataset.id = event.id;
  btn.dataset.date = event.date;
  btn.dataset.lod = lod;
  btn.dataset.shape = event.glyph;
  btn.dataset.venue = event.venueId || "";
  btn.classList.toggle("is-cancelled", !!event.cancelled);
  btn.classList.toggle("is-pinned", state.pinned === event.id);
  btn.style.setProperty("--venue", paint.venue);
  btn.style.setProperty("--edge", paint.edge);
  btn.style.setProperty("--ink", paint.ink);
  btn.style.setProperty("--stroke", `${entryStroke(event, Math.min(item.w, item.h)).toFixed(2)}px`);
  btn.style.setProperty("--grow", item.scale.toFixed(3));
  btn.style.width = `${Math.round(item.w)}px`;
  btn.style.height = `${Math.round(item.h)}px`;
  btn.setAttribute("aria-pressed", String(state.pinned === event.id));
  btn.setAttribute("aria-label", signLabel(event));

  const edge = el("span", "road-sign__edge");
  const face = el("span", "road-sign__face");
  if (lod !== "dot") face.append(el("span", "road-sign__title", event.title));
  btn.append(edge, face);

  btn.addEventListener("click", () => {
    if (suppressClick) return;
    if (event.date !== state.selected) {
      state.pinned = event.id;
      state.preview = null;
      select(event.date, { focusHeading: true, reason: `${event.title} is in front.` });
      return;
    }
    const held = state.pinned === event.id;
    state.pinned = held ? null : event.id;
    state.preview = state.pinned ? null : event.id;
    refreshPressed();
    paintSky();
    syncUrl();
  });
  return btn;
}

function bandName(date, depth) {
  const name = relative(date, todayIso());
  if (name === "Tonight" || name === "Tomorrow" || name === "Yesterday") return name;
  const day = Number(date.slice(8));
  if (depth === "far") return `${label.weekdayShort(date)} ${day}`;
  return label.medium(date);
}

function dateButton(date, count, header, depth) {
  const btn = el("button", "road__date");
  btn.type = "button";
  btn.dataset.date = date;
  btn.style.height = `${Math.round(header)}px`;
  const name = bandName(date, depth);
  const spoken = relative(date, todayIso());
  btn.setAttribute("aria-label", count ? `${spoken}, ${countLabel(count)}` : `${spoken}, nothing listed`);
  btn.append(el("span", "road__date-name", name));
  if (count) btn.append(el("span", "road__date-n", String(count)));
  btn.addEventListener("click", () => {
    if (!suppressClick) select(date, { focusHeading: true });
  });
  return btn;
}

function placeRoadSigns(events, frame) {
  const lane = el("div", "road__lane");
  lane.style.height = `${Math.round(frame.laneH)}px`;
  lane.style.width = `${Math.round(frame.laneW)}px`;
  if (!events.length) {
    if (frame.r === 0) lane.append(el("p", "road__lane-empty", "Nothing listed."));
    return lane;
  }

  const order = ranked(events);
  const spec = lodFor(frame.laneH, frame.laneW);
  const fitH = Math.max(18, frame.laneH - 4);
  const base = spec.lod === "full"
    ? Math.min(200, Math.max(96, frame.laneH * 0.84), frame.laneW * 0.42)
    : spec.lod === "title"
      ? Math.min(spec.h, 64, fitH)
      : 0;
  const boxesFor = lod => order.map(item => {
    if (lod === "dot" || fitH < 40 || base < 40) {
      const size = Math.round(16 + ((item.scale - 1) / (SCALE_MAX - 1)) * 14);
      const dot = Math.max(14, Math.min(size, fitH, frame.laneW));
      return { ...item, lod: "dot", w: dot, h: dot };
    }
    const grown = lod === "full" ? item.scale : Math.min(item.scale, 1.15);
    let side = Math.round((lod === "full" ? base : Math.min(base, spec.h)) * grown);
    side = Math.min(side, frame.laneW, fitH);
    if (side < 40) {
      const dot = Math.max(14, Math.min(24, fitH));
      return { ...item, lod: "dot", w: dot, h: dot };
    }
    return { ...item, lod, w: side, h: side };
  });

  let packed = packSigns(boxesFor(spec.lod), frame.laneW, frame.laneH, 8);
  let lod = spec.lod;
  if (packed.dot && spec.lod !== "dot") {
    lod = "dot";
    packed = packSigns(boxesFor("dot"), frame.laneW, frame.laneH, 6);
  }
  for (const item of packed.shown) lane.append(makeSign(item, item.lod || lod));
  if (packed.rest.length) {
    const more = el("span", "road-more", `+${packed.rest.length}`);
    more.title = `${packed.rest.length} more this night`;
    lane.append(more);
  }
  return lane;
}

function drawSurface(geom) {
  const cx = geom.W / 2;
  const half = geom.Wb / 2;
  const curb = half + Math.min(22, geom.W * 0.018);
  const top = geom.horizonY + 6;
  const ground = geom.groundY;
  const svg = (name, attrs) => {
    const node = document.createElementNS(SVG_NS, name);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
    return node;
  };
  els.surface.setAttribute("viewBox", `0 0 ${geom.W} ${geom.groundY}`);
  els.surface.replaceChildren(
    svg("polygon", { class: "road__curb", points: `${cx - curb},${ground} ${cx},${top} ${cx + curb},${ground}` }),
    svg("polygon", { class: "road__asphalt", points: `${cx - half},${ground} ${cx},${top + 10} ${cx + half},${ground}` }),
    svg("line", { class: "road__centre", x1: cx, y1: top + 36, x2: cx, y2: ground - 2 }),
  );
  els.road.style.setProperty("--horizon", `${geom.horizonY}px`);
  els.road.style.setProperty("--ground-y", `${ground}px`);
  els.road.style.setProperty("--stage", `${ground}px`);
  els.road.style.setProperty("--vanish-x", `${cx}px`);
  els.road.style.setProperty("--road-left", `${cx - half}px`);
  els.road.style.setProperty("--road-right", `${cx + half}px`);
}

function drawBands(frames, win) {
  els.rows.replaceChildren();
  const nights = win.nights || [];
  frames.forEach((frame, index) => {
    const date = nights[index];
    if (!date) return;
    const events = eventsOn(date);
    const band = el("div", "road-band");
    const depth = index === 0 ? "near" : index === 1 ? "mid" : "far";
    band.dataset.depth = depth;
    band.dataset.date = date;
    band.style.top = `${frame.y}px`;
    band.style.height = `${frame.height}px`;
    band.style.width = `${frame.near}px`;
    const inset = frame.near > 0 ? (frame.inset / frame.near) * 100 : 0;
    band.style.clipPath = `polygon(${inset}% 0, ${100 - inset}% 0, 100% 100%, 0 100%)`;
    band.append(placeRoadSigns(events, frame), dateButton(date, events.length, frame.header, depth));
    els.rows.append(band);
  });
  els.clear.hidden = nights.length > 0;
}

function updateFoot(win) {
  const events = eventsOn(win.selected || state.selected);
  const selected = win.selected || state.selected;
  const name = relative(selected, todayIso());
  els.groundLabel.textContent = name;
  const short = name === "Tonight" || name === "Tomorrow" || name === "Yesterday";
  els.groundWhen.hidden = !short;
  els.groundWhen.textContent = short ? label.medium(selected) : "";
  els.groundCount.textContent = events.length ? countLabel(events.length) : "";

  const next = neighbor(1);
  const prev = neighbor(-1);
  els.earlier.disabled = !prev;
  els.further.disabled = !next;
  const remain = win.remaining || 0;
  els.remain.hidden = remain <= 0;
  els.remain.textContent = remain > 0 ? String(remain) : "";
  els.further.setAttribute("aria-label", remain > 0 ? `Further, ${remain} later` : "Further");
  els.back.hidden = selected === todayIso();
  els.week.href = weekHref();
  if (document.activeElement !== els.jump) els.jump.value = selected >= todayIso() ? selected : todayIso();
}

function refreshPressed() {
  for (const btn of els.road.querySelectorAll(".road-sign")) {
    const on = btn.dataset.id === state.pinned;
    btn.classList.toggle("is-pinned", on);
    btn.setAttribute("aria-pressed", String(on));
  }
}

function availableKinds() {
  const kinds = new Set();
  for (const event of state.model.events) {
    if (event.date < todayIso()) continue;
    if (state.scope !== "all" && !event.night) continue;
    kinds.add(event.kind);
  }
  return kinds;
}

function paintKinds() {
  const available = availableKinds();
  const key = [...available].sort().join(",");
  if (key === state.kindKey) {
    for (const input of els.kinds.querySelectorAll("input")) input.checked = state.kinds.has(input.value);
    return;
  }
  state.kindKey = key;
  els.kinds.replaceChildren();
  for (const id of Object.keys(KINDS)) {
    if (!available.has(id)) continue;
    const row = el("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "kind";
    input.value = id;
    input.checked = state.kinds.has(id);
    row.append(input, document.createTextNode(` ${KINDS[id].label}`));
    els.kinds.append(row);
  }
}

function reflectForm() {
  const scope = els.filters.querySelector(`input[name="scope"][value="${state.scope}"]`);
  if (scope) scope.checked = true;
  els.filters.querySelector('input[name="free"]').checked = state.free;
  els.filters.querySelector('input[name="hideCancelled"]').checked = state.hideCancelled;
  paintKinds();
}

function restoreFocus(active, focusHeading) {
  if (focusHeading) {
    els.heading.focus({ preventScroll: true });
    return;
  }
  if (!active || active.isConnected) return;
  const signId = active.dataset?.id || active.closest?.(".road-sign")?.dataset.id;
  const date = active.dataset?.date;
  if (signId) {
    els.road.querySelector(`.road-sign[data-id="${CSS.escape(signId)}"]`)?.focus({ preventScroll: true });
    return;
  }
  if (date) els.road.querySelector(`[data-date="${CSS.escape(date)}"]`)?.focus({ preventScroll: true });
}

function render({ speak = false, focusHeading = false, reason = "" } = {}) {
  const width = els.road.clientWidth;
  const height = els.road.clientHeight;
  if (width < 20 || height < 50) {
    if (resizeTries++ < 40) requestAnimationFrame(() => render({ speak, focusHeading, reason }));
    return;
  }
  const portrait = height > width;
  if (portrait && !state.portrait) els.filtersWrap.open = false;
  state.portrait = portrait;
  document.documentElement.dataset.road = portrait ? "portrait" : "landscape";
  if (reducedMotion()) document.documentElement.dataset.motion = document.documentElement.dataset.motion || "reduce";

  const active = document.activeElement;
  const exact = state.dates.indexOf(state.selected);
  const stageH = els.stage.clientHeight;
  const stageW = els.stage.clientWidth || width;
  if (stageH < 80) {
    if (resizeTries++ < 40) requestAnimationFrame(() => render({ focusHeading, reason }));
    return;
  }
  resizeTries = 0;
  // Street-level defaults live in perspective(); nights fill the road from your feet up.
  const geom = perspective(stageW, stageH);
  const later = state.dates.filter(date => date > state.selected);
  const nightBudget = exact >= 0
    ? Math.min(12, Math.max(4, state.dates.length - exact))
    : Math.min(12, Math.max(4, later.length + 1));
  const frames = bandFrames(geom, nightBudget);
  const follow = Math.max(0, frames.length - 1);
  const win = exact >= 0
    ? standAt(state.dates, exact, frames.length)
    : {
      selected: state.selected,
      road: later.slice(0, follow),
      nights: [state.selected, ...later.slice(0, follow)].filter(Boolean).slice(0, frames.length),
      remaining: Math.max(0, later.length - follow),
    };

  drawSurface(geom);
  drawBands(frames, win);
  updateFoot(win);
  paintSky();
  paintKinds();
  restoreFocus(active, focusHeading);
  if (speak) {
    const name = relative(state.selected, todayIso());
    const count = eventsOn(state.selected).length;
    announce(reason || `${name}. ${count ? countLabel(count) : "Nothing listed this night."}`);
  }
}

function select(date, { focusHeading = false, reason = "" } = {}) {
  if (!isValidDate(date) || date < todayIso()) date = todayIso();
  const day = eventsOn(date);
  if (state.pinned && !day.some(event => event.id === state.pinned)) state.pinned = null;
  if (state.selected !== date) state.preview = null;
  state.selected = date;
  const name = relative(date, todayIso());
  const count = day.length;
  const said = reason || `${name}. ${count ? countLabel(count) : "Nothing listed this night."}`;
  render({ speak: true, focusHeading, reason: said });
  syncUrl();
}

function step(dir, focusHeading) {
  const date = neighbor(dir);
  if (date) select(date, { focusHeading });
}

function onFilterChange() {
  const data = new FormData(els.filters);
  state.scope = data.get("scope") === "all" ? "all" : "nights";
  state.free = data.has("free");
  state.hideCancelled = data.has("hideCancelled");
  state.kinds = new Set([...data.getAll("kind")].filter(kind => KINDS[kind]));
  for (const kind of [...state.kinds]) {
    if (state.scope !== "all" && !state.model.events.some(event => event.kind === kind && event.night && event.date >= todayIso())) {
      state.kinds.delete(kind);
    }
  }
  recompute();
  if (state.preview && !passes(byId(state.preview))) state.preview = null;
  if (state.pinned && !passes(byId(state.pinned))) state.pinned = null;
  paintKinds();
  const scopeName = state.scope === "all" ? "Showing everything." : "Showing nights out.";
  render({ speak: true, reason: scopeName });
  syncUrl();
}

function stewardId() {
  try {
    const raw = localStorage.getItem(STEWARD_PAYLOAD);
    if (raw) {
      const parsed = JSON.parse(raw);
      const id = parsed?.stewardId || parsed?.steward_id;
      if (id) return String(id);
    }
  } catch { /* fall through to the local id */ }
  try {
    let id = localStorage.getItem(STEWARD_LOCAL);
    if (!id) {
      id = crypto.randomUUID?.() || `steward-${Date.now().toString(36)}-${Math.random().toString(16).slice(2)}`;
      localStorage.setItem(STEWARD_LOCAL, id);
    }
    return id;
  } catch {
    return "";
  }
}

function persistVote(id, direction) {
  if (direction !== "+" && direction !== "retract") return;
  if (!isStewardActive()) return;
  const steward = stewardId();
  if (!steward) return;
  fetch("/api/action", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({
      name: "vote",
      context: { eventId: id, direction, steward_id: steward, verified: true },
    }),
  }).catch(() => {});
}

function onBodies(event) {
  const detail = event.detail || {};
  const item = byId(detail.id);
  if (!item || (detail.direction !== "+" && detail.direction !== "retract")) return;
  item.bodies = Math.max(0, Number(detail.bodies) || 0);
  if (detail.direction === "+") state.voted.add(item.id);
  else state.voted.delete(item.id);
  render();
  persistVote(item.id, detail.direction);
}

function onKey(event) {
  const tag = event.target?.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
  if (event.key === "ArrowDown") { event.preventDefault(); step(1, true); }
  else if (event.key === "ArrowUp") { event.preventDefault(); step(-1, true); }
  else if (event.key === "Home") { event.preventDefault(); select(todayIso(), { focusHeading: true }); }
  else if (event.key === "Escape" && state.pinned) {
    state.pinned = null;
    state.preview = null;
    refreshPressed();
    paintSky();
    announce("Unpinned.");
    syncUrl();
  } else if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
    const signs = [...els.road.querySelectorAll(".road-sign")];
    const index = signs.indexOf(document.activeElement);
    if (index < 0) return;
    event.preventDefault();
    const next = signs[index + (event.key === "ArrowRight" ? 1 : -1)];
    next?.focus();
  }
}

function bindTravel() {
  els.earlier.addEventListener("click", () => step(-1, true));
  els.further.addEventListener("click", () => step(1, true));
  els.back.addEventListener("click", () => select(todayIso(), { focusHeading: true }));
  els.jump.min = todayIso();
  els.jump.addEventListener("change", () => {
    if (isValidDate(els.jump.value)) select(els.jump.value, { focusHeading: true });
  });
  els.filters.addEventListener("change", onFilterChange);
  els.road.addEventListener("pointerover", event => {
    const sign = event.target.closest?.(".road-sign");
    if (!sign?.dataset.id || state.pinned) return;
    if (state.preview === sign.dataset.id) return;
    state.preview = sign.dataset.id;
    paintSky();
  });
  els.road.addEventListener("pointerout", event => {
    const sign = event.target.closest?.(".road-sign");
    if (!sign) return;
    const to = event.relatedTarget;
    if (to?.closest?.(".road-sign")) return;
    if (state.pinned) return;
    state.preview = null;
    paintSky();
  });
  els.road.addEventListener("focusin", event => {
    const sign = event.target.closest?.(".road-sign");
    if (!sign?.dataset.id || state.pinned) return;
    if (state.preview === sign.dataset.id) return;
    state.preview = sign.dataset.id;
    paintSky();
  });
  els.road.addEventListener("focusout", event => {
    const sign = event.target.closest?.(".road-sign");
    if (!sign) return;
    const to = event.relatedTarget;
    if (to?.closest?.(".road-sign")) return;
    if (to && els.info.contains(to)) return;
    if (state.pinned) return;
    state.preview = null;
    paintSky();
  });

  let drag = null;
  els.stage.addEventListener("pointerdown", event => {
    if (event.button !== 0) return;
    if (event.target.closest("button, a, input, label, summary")) return;
    drag = { x: event.clientX, y: event.clientY, id: event.pointerId };
  });
  window.addEventListener("pointerup", event => {
    if (!drag || event.pointerId !== drag.id) return;
    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;
    drag = null;
    if (Math.abs(dy) < 48 || Math.abs(dy) < Math.abs(dx)) return;
    suppressClick = true;
    step(dy < 0 ? 1 : -1, false);
    setTimeout(() => { suppressClick = false; }, 350);
  });
  els.road.addEventListener("click", event => {
    if (!suppressClick) return;
    suppressClick = false;
    event.preventDefault();
    event.stopPropagation();
  }, true);
  els.stage.addEventListener("wheel", event => {
    if (event.target.closest(".road__info, .road__filters")) return;
    event.preventDefault();
    const now = performance.now();
    if (now - lastWheel < 320) return;
    lastWheel = now;
    step(event.deltaY > 0 ? 1 : -1, false);
  }, { passive: false });
  document.addEventListener("keydown", onKey);
  document.addEventListener("nc:bodies", onBodies);
  window.addEventListener("popstate", () => {
    readUrl();
    recompute();
    bootSelection();
    state.shownKey = null;
    state.skyId = null;
    reflectForm();
    render({ speak: true });
  });
  const observer = new ResizeObserver(() => render());
  observer.observe(els.road);
}

function start(model) {
  state.model = model;
  readUrl();
  applyDemo(model.events);
  loadVotes();
  recompute();
  bootSelection();
  reflectForm();
  els.jump.min = todayIso();
  els.filtersWrap.open = false;
  if (model.source === "sample") {
    els.source.hidden = false;
    els.source.textContent = "Sample calendar. The live list is offline.";
  }
  bindTravel();
  render({ speak: true });
  syncUrl();
}

loadCalendar().then(start).catch(() => {
  els.groundLabel.textContent = "The calendar didn't load.";
});
