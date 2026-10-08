// Calendar data adapter. The ONLY place the front-end touches the backend's
// shape. It reads the A2UI data model the nightcal server already publishes
// (GET /api/model -> { updateDataModel: { value: { place, venues, events, ui } } })
// and returns a renderer-neutral CalendarModel that the DOM components and
// the 3D scene both consume. No backend changes are needed or made.

import { today } from "./dates.js";

export const KINDS = {
  music: { label: "Live music", tone: "music", glyph: "circle" },
  comedy: { label: "Comedy", tone: "comedy", glyph: "diamond" },
  show: { label: "Show", tone: "show", glyph: "square" },
  trivia: { label: "Trivia", tone: "trivia", glyph: "triangle" },
  trucks: { label: "Food trucks", tone: "food", glyph: "hexagon" },
  other: { label: "Other", tone: "other", glyph: "ring" },
};
/** Kinds counted as a night out (same set the server uses for its "Shows" scope). */
export const NIGHT_KINDS = new Set(["music", "comedy", "show", "trivia"]);
export const SCOPES = { nights: "Nights out", all: "Everything" };

export const kindOf = k => KINDS[k] || KINDS.other;

const API = "/api/model";
const SAMPLE = new URL("../../data/sample-model.json", import.meta.url).href;
let cached = null;

/**
 * Load the calendar. Tries the live API first, then the bundled sample so
 * embeds and previews still render when the API is unreachable.
 * Resolves to a CalendarModel; never rejects.
 */
export function loadCalendar({ api = API, timeoutMs = 4000 } = {}) {
  if (cached) return cached;
  cached = (async () => {
    const live = await fetchJSON(api, timeoutMs);
    if (live) return normalize(unwrap(live), "live");
    const sample = await fetchJSON(SAMPLE, timeoutMs);
    return normalize(unwrap(sample || {}), "sample");
  })();
  return cached;
}

async function fetchJSON(url, timeoutMs) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: ctrl.signal, headers: { Accept: "application/json" } });
    if (!res.ok || !(res.headers.get("content-type") || "").includes("json")) return null;
    return await res.json();
  } catch { return null; } finally { clearTimeout(timer); }
}

const unwrap = msg => msg?.updateDataModel?.value || msg || {};

/** Pure: raw server model -> CalendarModel. Exported for tests and the 3D page. */
export function normalize(raw, source = "live") {
  const venues = (raw.venues || []).map(v => ({
    id: v.id, name: v.name, address: v.address || "", lat: v.lat, lon: v.lon,
    amenity: v.amenity || "", music: !!v.music, contact: v.contact || {},
  }));
  const venuesById = new Map(venues.map(v => [v.id, v]));
  const events = (raw.events || [])
    .filter(e => !e.suppressed && e.date)
    .map(e => {
      const kind = KINDS[e.kind] ? e.kind : "other";
      const meta = KINDS[kind];
      return {
        id: e.id,
        title: (e.title || "").trim() || "Untitled",
        date: e.date,
        start: e.startLabel || "",
        end: e.endLabel || "",
        minutes: Number.isFinite(e.minutes) ? e.minutes : 24 * 60,
        kind, kindLabel: meta.label, tone: meta.tone, glyph: meta.glyph,
        night: NIGHT_KINDS.has(kind),
        venueId: e.venueId || "",
        venueName: venuesById.get(e.venueId)?.name || e.venue || "",
        url: safeUrl(e.sourceUrl),
        sourceName: e.sourceName || "",
        checks: (e.checks || []).map(c => ({ name: c.name, url: safeUrl(c.url) })).filter(c => c.url),
        image: safeUrl(e.image),
        performers: (e.performers || []).map(p => p.name).filter(Boolean),
        up: e.up || 0, down: e.down || 0, score: e.score || 0,
        needsReview: !!e.needsReview,
        startsAt: e.startsAt || "", endsAt: e.endsAt || "",
      };
    })
    .sort((a, b) => a.date.localeCompare(b.date) || a.minutes - b.minutes || a.title.localeCompare(b.title));

  const counts = new Map();
  for (const e of events) counts.set(e.venueId, (counts.get(e.venueId) || 0) + 1);
  // Rooms are listed only when something is on there. A closed room with no
  // listing never appears; one with a cited listing appears because the
  // listing is the evidence (the server applies the same rule).
  for (const v of venues) v.eventCount = counts.get(v.id) || 0;

  const ui = raw.ui || {};
  return {
    source, place: raw.place || "",
    today: today(),
    venues, venuesById,
    events, eventsById: new Map(events.map(e => [e.id, e])),
    notes: {
      status: ui.status || "",
      closed: ui.closedNote || "",
      attribution: ui.attribution || "Rooms from OpenStreetMap contributors.",
    },
  };
}

function safeUrl(u) {
  if (!u || typeof u !== "string") return "";
  try { const url = new URL(u); return url.protocol === "https:" || url.protocol === "http:" ? url.href : ""; } catch { return ""; }
}

/** Events passing the reader's filters. */
export function filterEvents(model, { scope = "nights", venueId = "" } = {}) {
  return model.events.filter(e => (scope === "all" || e.night) && (!venueId || e.venueId === venueId));
}

/** Rooms worth offering in the filter: ones with at least one event in scope. */
export function roomsWithEvents(model, { scope = "nights" } = {}) {
  const ids = new Set(filterEvents(model, { scope }).map(e => e.venueId));
  return model.venues.filter(v => ids.has(v.id)).sort((a, b) => a.name.localeCompare(b.name));
}

export function byDate(events) {
  const map = new Map();
  for (const e of events) { if (!map.has(e.date)) map.set(e.date, []); map.get(e.date).push(e); }
  return map;
}

/** Next date on or after `from` that has an event, or "". */
export function nextDateWithEvents(events, from) {
  return events.find(e => e.date >= from)?.date || "";
}
