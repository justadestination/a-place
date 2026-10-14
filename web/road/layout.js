// Pure layout for the NightCal road. No document, no network.
//
// Sign size is Decision 005 (billboardScale): a logarithmic tally curve
// with a hard ceiling. A small share nudge makes a show that owns its
// night a little larger than one that shares the night. The nudge cannot
// jump a single +1 to the ceiling.

import { billboardScale } from "../components/event-card/event-card.js";

export const SCALE_MAX = 1.75;
const K = 1.55;

/** @param {number} bodies @param {{ dayTotal?: number, count?: number }} [ctx] */
export function signScale(bodies, { dayTotal = 0, count = 1 } = {}) {
  const n = Math.max(0, Number(bodies) || 0);
  if (n <= 0 || dayTotal <= 0) return 1;
  const base = billboardScale(n);
  const peers = Math.max(1, Number(count) || 1);
  const share = n / dayTotal;
  const fair = 1 / peers;
  const nudge = 1 + 0.12 * Math.max(-0.5, Math.min(0.5, share - fair));
  return Math.min(SCALE_MAX, Math.max(1, base * nudge));
}

/**
 * Level of detail from the on-screen lane, in CSS pixels after perspective.
 * A full board has to fit the nearest row on a laptop, not a fixed 4× sprite.
 */
export function lodFor(laneH, laneW) {
  const h = Math.max(0, Number(laneH) || 0);
  const w = Math.max(0, Number(laneW) || 0);
  if (h >= 88 && w >= 112) {
    const maxH = Math.min(112, h * 0.82);
    return {
      lod: "full",
      w: Math.min(220, Math.max(128, w * 0.46)),
      h: Math.min(96, maxH / SCALE_MAX),
    };
  }
  if (h >= 46 && w >= 64) {
    const maxH = Math.min(58, h * 0.78);
    return {
      lod: "title",
      w: Math.min(168, Math.max(88, w * 0.5)),
      h: Math.min(48, maxH / SCALE_MAX),
    };
  }
  const dot = Math.max(14, Math.min(26, Math.min(h, w) * 0.55 || 14));
  return { lod: "dot", w: dot, h: dot };
}

/** Listing dates from today forward, plus today even when it is empty. Gaps are dropped. */
export function listingDates(events, today) {
  const dates = new Set();
  for (const e of events || []) {
    if (e?.date && e.date >= today) dates.add(e.date);
  }
  if (today) dates.add(today);
  return [...dates].sort();
}

/**
 * Travel window. `index` is the night standing in the foreground.
 * The road draws the following listing dates, `count` of them.
 */
export function windowAt(dates, index, count) {
  const list = dates || [];
  const max = Math.max(0, list.length - 1);
  const i = Math.max(0, Math.min(Number(index) || 0, max));
  const take = Math.max(0, count | 0);
  const road = list.slice(i + 1, i + 1 + take);
  return {
    index: i,
    selected: list[i] || "",
    road,
    earlier: i > 0,
    later: i + 1 + road.length < list.length,
    remaining: Math.max(0, list.length - (i + 1 + road.length)),
  };
}

/** Bodies the sign should use. A saved local vote counts as one when the server has not. */
export function effectiveBodies(event, voted = false) {
  const server = Math.max(0, Number(event?.bodies) || 0);
  return voted ? Math.max(server, 1) : server;
}

/**
 * Nights drawn on the road, nearest first. `index` is the night you are
 * standing in, so it is the closest row, not a separate foreground.
 */
export function standAt(dates, index, count) {
  const take = Math.max(0, count | 0);
  const win = windowAt(dates, index, Math.max(0, take - 1));
  const nights = [];
  if (take > 0 && win.selected) nights.push(win.selected);
  for (const date of win.road) {
    if (nights.length >= take) break;
    nights.push(date);
  }
  return { ...win, nights };
}

function hexToRgb(hex) {
  const n = Number.parseInt(String(hex).replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function relLum(hex) {
  const lin = hexToRgb(hex).map(channel => {
    const s = channel / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
}

function mixHex(hex, toward, amount) {
  const a = hexToRgb(hex);
  const b = hexToRgb(toward);
  const t = Math.max(0, Math.min(1, amount));
  const mixed = a.map((channel, i) => Math.round(channel + (b[i] - channel) * t));
  return `#${mixed.map(channel => channel.toString(16).padStart(2, "0")).join("")}`;
}

function contrast(a, b) {
  const left = relLum(a);
  const right = relLum(b);
  const [hi, lo] = left > right ? [left, right] : [right, left];
  return (hi + 0.05) / (lo + 0.05);
}

/**
 * Lit glass for venues. Color is the venue, so these read as night tubes on
 * asphalt, not the kind-paper tones. No pink, no cyan.
 */
export const VENUE_COLORS = [
  "#FF6B5C",
  "#FF8A3D",
  "#FFB020",
  "#E8C84A",
  "#C8E04A",
  "#7BC96A",
  "#3FAE7A",
  "#2F9E8C",
  "#3D7CFF",
  "#5A6BFF",
  "#7A5CFF",
  "#A56BFF",
  "#C9A0FF",
  "#FF5A3A",
  "#D4A05A",
  "#6A9E4A",
  "#4A8AB8",
  "#6B5CA8",
  "#B87C4A",
  "#8A6B3A",
];

/** Tall posters sit inside the bay; wide posters fill it. */
export function posterFit(naturalW, naturalH) {
  const width = Math.max(1, Number(naturalW) || 1);
  const height = Math.max(1, Number(naturalH) || 1);
  return height > width * 1.05 ? "contain" : "cover";
}

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
  // Invert perspective-like: small t -> small depth (near).
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

/** Fill, a contrasting edge, and ink that stays readable on the fill. */
export function venuePaint(venueId, venueIds = []) {
  const ids = [...new Set((venueIds || []).filter(Boolean))].sort();
  const index = ids.indexOf(venueId);
  const venue = index < 0 ? "#6F6A5E" : VENUE_COLORS[index % VENUE_COLORS.length];
  const darkFill = relLum(venue) <= 0.36;
  const edge = mixHex(venue, darkFill ? "#F4F1E8" : "#0B0B0C", darkFill ? 0.5 : 0.42);
  const ink = contrast(venue, "#121214") >= contrast(venue, "#F7F4EC") ? "#121214" : "#F7F4EC";
  return { venue, edge, ink };
}

function entryDollars(event) {
  const price = event?.price;
  if (price == null || price === "") return null;
  if (typeof price === "number" && Number.isFinite(price)) return price;
  const text = String(price).trim();
  if (!text) return null;
  if (/^\s*(free|\$0(?:\.00)?)\s*$/i.test(text)) return 0;
  const match = text.replace(/,/g, "").match(/\$?\s*(\d+(?:\.\d+)?)/);
  return match ? Number(match[1]) : null;
}

/**
 * Border thickness in CSS pixels before the small-sign cap.
 * Free is the thinnest. An unlisted price is not drawn as expensive.
 * Known dollars step up: under $15, under $30, under $50, then the rest.
 */
export function entryWeight(event) {
  if (event?.free) return 1;
  const dollars = entryDollars(event);
  if (dollars == null) return 2;
  if (dollars <= 0) return 1;
  if (dollars < 15) return 3;
  if (dollars < 30) return 5;
  if (dollars < 50) return 7;
  return 9;
}

/** What the sky should say. Never invents a price the listing does not have. */
export function entryLabel(event) {
  if (event?.free) return "Free";
  const dollars = entryDollars(event);
  if (dollars == null) return "Entry not listed";
  if (dollars <= 0) return "Free";
  const rounded = Math.round(dollars * 100) / 100;
  return Number.isInteger(rounded) ? `$${rounded}` : `$${rounded.toFixed(2)}`;
}

/** Thickness actually drawn. A far sign keeps at least a hairline, and at most ~12% of its box. */
export function entryStroke(event, signPx) {
  const weight = entryWeight(event);
  const cap = Math.max(1, (Number(signPx) || 0) * 0.12);
  return Math.min(weight, cap);
}

export function perspective(W, H, { ground = null, horizon = null, road = null, k = null } = {}) {
  const width = Math.max(1, Number(W) || 1);
  const height = Math.max(1, Number(H) || 1);
  const portrait = height > width;
  // Street-level: eye-height horizon, road from your feet to the vanishing point.
  const horizonY = horizon == null ? Math.round(height * (portrait ? 0.26 : 0.32)) : Math.round(horizon);
  const groundY = ground == null ? height : Math.round(ground);
  const G = Math.max(1, groundY - horizonY);
  const fraction = road == null
    ? (portrait ? 0.64 : 0.72)
    : Math.max(0.18, Math.min(0.92, Number(road) || 0.46));
  const Wb = Math.min(width * fraction, G * 2.15);
  const depth = k == null ? (portrait ? 3.1 : 3.5) : Math.max(0.45, Number(k) || K);
  const p = d => 1 / (1 + d / depth);
  return {
    W: width,
    H: height,
    portrait,
    horizonY,
    groundY,
    G,
    Wb,
    k: depth,
    p,
    yAt: d => horizonY + G * p(d),
    widthAt: d => Wb * p(d),
  };
}

/**
 * On-screen bands from the ground up toward the horizon. Heights are weighted
 * in screen space so the nights fill the road (street-level), while width still
 * follows perspective: width = Wb * (y - horizon) / G.
 */
export function bandFrames(g, count = 16) {
  const frames = [];
  const want = Math.max(0, count | 0);
  if (want === 0 || g.G < 24) return frames;
  const tip = Math.min(18, Math.round(g.G * 0.035));
  const span = Math.max(18, g.G - tip);
  const minH = 16;
  let n = Math.min(want, Math.max(1, Math.floor(span / minH)));
  const heightsFor = rows => {
    const weights = Array.from({ length: rows }, (_, i) => 0.55 + (rows - i) ** 1.15);
    const weightSum = weights.reduce((sum, w) => sum + w, 0);
    return weights.map(w => span * (w / weightSum));
  };
  while (n > 1 && heightsFor(n).some(h => h < minH)) n -= 1;
  const heights = heightsFor(n);
  const widthAtY = y => {
    const t = Math.max(0.02, Math.min(1, (y - g.horizonY) / g.G));
    return g.Wb * t;
  };
  let nearY = g.groundY;
  for (let r = 0; r < n; r++) {
    const height = heights[r];
    const farY = nearY - height;
    const near = widthAtY(nearY);
    const far = widthAtY(farY);
    const header = Math.min(28, Math.max(10, height * 0.22));
    const laneH = height - header;
    if (laneH < 6) break;
    frames.push({
      r,
      y: farY,
      height,
      near,
      far,
      inset: Math.max(0, (near - far) / 2),
      header,
      laneH,
      laneW: Math.max(12, far - 16),
    });
    nearY = farY;
  }
  return frames;
}

/**
 * Pack signs into a lane. `items` are in priority order (most attended first).
 * Whatever does not fit is `rest` (the caller draws a "+N" for it).
 * `dot` means even the first sign is taller than the lane.
 */
export function packSigns(items, laneW, laneH, gap = 8) {
  const list = items || [];
  const w = Number(laneW) || 0;
  const h = Number(laneH) || 0;
  if (!list.length || w <= 0 || h <= 0) return { shown: [], rest: list.slice(), dot: false };
  const place = boxes => {
    let x = 0;
    let y = 2;
    let rowH = 0;
    for (const box of boxes) {
      const ew = Math.min(box.w, w);
      const eh = box.h;
      if (eh > h) return false;
      if (x > 0 && x + ew > w + 0.5) {
        y += rowH + gap;
        x = 0;
        rowH = 0;
      }
      if (y + eh > h + 0.5) return false;
      x += ew + gap;
      rowH = Math.max(rowH, eh);
    }
    return true;
  };
  if (place(list)) return { shown: list.slice(), rest: [], dot: false };
  let n = 0;
  while (n < list.length && place(list.slice(0, n + 1))) n += 1;
  if (n === 0) return { shown: [], rest: list.slice(), dot: true };
  return { shown: list.slice(0, n), rest: list.slice(n), dot: false };
}
