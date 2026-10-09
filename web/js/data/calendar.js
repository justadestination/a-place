// Calendar data adapter. The ONLY place the front-end touches the backend's
// shape. It reads the A2UI data model the nightcal server already publishes
// (GET /api/model -> { updateDataModel: { value: { place, venues, events, ui } } })
// and returns a renderer-neutral CalendarModel that the DOM components and
// the 3D scene both consume. No backend changes are needed or made.

import { today } from "./dates.js";
import { computeLifecycle } from "./lifecycle.js";
import { formatLocalizedTime, formatTimeRange, getTimezoneAbbr, DEFAULT_TIMEZONE } from "./tz.js";


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

/**
 * Task 2.3: Closed venues are never listed. Data layer flags them;
 * if the flag doesn't exist on incoming data, detect and log it.
 */
export function isClosedVenue(v) {
  if (!v) return false;
  if (v.closed || v.is_closed) return true;
  if (typeof v.status === "string" && v.status.toLowerCase() === "closed") return true;
  if (typeof v.amenity === "string" && v.amenity.toLowerCase() === "closed") return true;
  if (v.meta && (v.meta.closed || v.meta.is_closed)) return true;
  return false;
}

/** Pure: raw server model -> CalendarModel. Exported for tests and the 3D page. */
export function normalize(raw, source = "live", { today: overrideToday } = {}) {
  const closedVenueIds = new Set();
  for (const v of raw.venues || []) {
    if (isClosedVenue(v)) {
      closedVenueIds.add(v.id);
      console.log(`[calendar] Closed venue filtered: ${v.name} (${v.id})`);
    }
  }

  const venues = (raw.venues || [])
    .filter(v => !closedVenueIds.has(v.id))
    .map(v => ({
      id: v.id, name: v.name, address: v.address || "", lat: v.lat, lon: v.lon,
      amenity: v.amenity || "", music: !!v.music, contact: v.contact || {},
      timezone: v.timezone || DEFAULT_TIMEZONE,
      closed: false, is_closed: false,
    }));
  const venuesById = new Map(venues.map(v => [v.id, v]));
  const events = (raw.events || [])
    .filter(e => !e.suppressed && e.date && !closedVenueIds.has(e.venueId))
    .map(e => {
      const kind = KINDS[e.kind] ? e.kind : "other";
      const meta = KINDS[kind];
      const venue = venuesById.get(e.venueId);
      const tz = e.timezone || venue?.timezone || DEFAULT_TIMEZONE;
      const tzAbbr = e.tzAbbr || (e.startsAt ? getTimezoneAbbr(e.startsAt, tz) : "");
      const localizedStart = e.startsAt ? formatLocalizedTime(e.startsAt, tz, { includeTz: true }) : (e.startLabel || "");
      const localizedTime = e.startsAt ? formatTimeRange(e.startsAt, e.endsAt, tz) : [e.startLabel, e.endLabel].filter(Boolean).join(" – ");

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
        venueName: venue?.name || e.venue || "",
        timezone: tz,
        tzAbbr,
        localizedStart,
        localizedTime,
        timeDisplay: localizedTime,
        url: safeUrl(e.sourceUrl),
        sourceName: e.sourceName || "",
        checks: (e.checks || []).map(c => ({ name: c.name, url: safeUrl(c.url) })).filter(c => c.url),
        image: safeUrl(e.image),
        performers: (e.performers || []).map(p => p.name).filter(Boolean),
        up: e.up || 0, down: e.down || 0, score: e.score || 0,
        bodies: Number.isFinite(e.bodies) ? e.bodies : (Number.isFinite(e.up) ? e.up : 0),
        verifiedBodies: Number.isFinite(e.verified_bodies) ? e.verified_bodies : 0,
        unverifiedBodies: Number.isFinite(e.unverified_bodies) ? e.unverified_bodies : 0,
        needsReview: !!e.needsReview,
        startsAt: e.startsAt || "", endsAt: e.endsAt || "",
        lifecycle: e.lifecycle || computeLifecycle(e.startsAt, e.endsAt).state,
        happeningNow: Boolean(e.happeningNow ?? computeLifecycle(e.startsAt, e.endsAt).happeningNow),
        isPast: Boolean(e.isPast ?? computeLifecycle(e.startsAt, e.endsAt).isPast),
        isArchived: Boolean(e.isArchived ?? computeLifecycle(e.startsAt, e.endsAt).isArchived),
        isRecurring: Boolean(e.isRecurring || e.is_recurring || e.recurrence),
        recurrence: e.recurrence || null,
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
    today: overrideToday || raw.today || today(),
    venues, venuesById,
    events, eventsById: new Map(events.map(e => [e.id, e])),
    notes: {
      status: ui.status || "",
      closed: "", // Closed venues never listed in public notes
      attribution: ui.attribution || "Rooms from OpenStreetMap contributors.",
    },
  };
}

function safeUrl(u) {
  if (!u || typeof u !== "string") return "";
  try { const url = new URL(u); return url.protocol === "https:" || url.protocol === "http:" ? url.href : ""; } catch { return ""; }
}

/** Events passing the reader's filters. */
export function filterEvents(model, { scope = "nights", venueId = "", kind = "" } = {}) {
  return model.events.filter(e =>
    (scope === "all" || e.night) &&
    (!venueId || e.venueId === venueId) &&
    (!kind || e.kind === kind)
  );
}

/** Rooms worth offering in the filter: ones with at least one event in scope. */
export function roomsWithEvents(model, { scope = "nights" } = {}) {
  const ids = new Set(filterEvents(model, { scope }).map(e => e.venueId));
  return model.venues.filter(v => ids.has(v.id)).sort((a, b) => a.name.localeCompare(b.name));
}

/** Tags/kinds worth offering in the filter: ones with at least one event in scope. */
export function kindsWithEvents(model, { scope = "nights", venueId = "" } = {}) {
  const events = model.events.filter(e => (scope === "all" || e.night) && (!venueId || e.venueId === venueId));
  const activeKinds = new Set(events.map(e => e.kind));
  return Object.entries(KINDS)
    .filter(([k]) => activeKinds.has(k))
    .map(([id, meta]) => ({ id, label: meta.label }));
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
