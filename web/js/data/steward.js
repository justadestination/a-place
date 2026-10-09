// Steward Personalization Hooks (Task 2.7)
// When a Steward payload is provided (e.g. from user credentials or local store),
// the calendar merges personal items, hides muted venues, highlights earmarked events,
// and surfaces "brought to your attention" items.
//
// Invariant: The default view renders fully without any steward payload.
// All four behaviors degrade gracefully on empty, partial, or adversarial payloads.

import { KINDS } from "./calendar.js";

/**
 * Expected Steward Payload Schema:
 * {
 *   stewardId: string,
 *   name: string,
 *   personalEvents?: Array<{ id, title, date, start?, end?, minutes?, kind?, venueName? }>,
 *   mutedVenues?: string[],         // venue IDs whose public events are hidden
 *   earmarkedEvents?: string[],     // event IDs the reader has saved / earmarked
 *   broughtToAttention?: Array<{    // items surfaced by the community/operators
 *     id: string,
 *     eventId: string,
 *     reason: string,
 *     flaggedBy?: string
 *   }>
 * }
 */

/**
 * Pure function: Apply steward personalization to a normalized CalendarModel.
 * @param {import("./calendar.js").CalendarModel} model
 * @param {object|null} payload
 * @param {object} options
 * @param {boolean} [options.enabled=true] - Feature flag toggle
 * @returns {import("./calendar.js").CalendarModel} personalized calendar model
 */
export function applyStewardPersonalization(model, payload, { enabled = true } = {}) {
  // If disabled, payload missing, or not an object: return model untouched
  if (!enabled || !payload || typeof payload !== "object") {
    return { ...model, steward: null, hasSteward: false };
  }

  // 1. Sanitize payload fields defensively against adversarial inputs
  const mutedSet = new Set(
    Array.isArray(payload.mutedVenues)
      ? payload.mutedVenues.filter(id => typeof id === "string" && id.trim())
      : []
  );

  const earmarkedSet = new Set(
    Array.isArray(payload.earmarkedEvents)
      ? payload.earmarkedEvents.filter(id => typeof id === "string" && id.trim())
      : []
  );

  const attentionMap = new Map();
  if (Array.isArray(payload.broughtToAttention)) {
    for (const item of payload.broughtToAttention) {
      if (item && typeof item === "object" && typeof item.eventId === "string") {
        attentionMap.set(item.eventId, {
          id: String(item.id || item.eventId),
          reason: typeof item.reason === "string" ? item.reason : "Surfaced by steward",
          flaggedBy: typeof item.flaggedBy === "string" ? item.flaggedBy : "",
        });
      }
    }
  }

  // 2. Hide muted venues from existing events
  const filteredExistingEvents = model.events
    .filter(e => !mutedSet.has(e.venueId))
    .map(e => {
      const isEarmarked = earmarkedSet.has(e.id);
      const attention = attentionMap.get(e.id);
      return {
        ...e,
        isEarmarked,
        isAttention: !!attention,
        attentionReason: attention ? attention.reason : "",
        attentionBy: attention ? attention.flaggedBy : "",
      };
    });

  // 3. Merge personal calendar events
  const personalEvents = [];
  if (Array.isArray(payload.personalEvents)) {
    for (const pe of payload.personalEvents) {
      if (!pe || typeof pe !== "object" || !pe.id || !pe.date || typeof pe.date !== "string") {
        continue;
      }
      const kind = KINDS[pe.kind] ? pe.kind : "other";
      const meta = KINDS[kind];
      personalEvents.push({
        id: String(pe.id),
        title: (pe.title || "").trim() || "Personal Event",
        date: pe.date,
        start: pe.start || "",
        end: pe.end || "",
        minutes: Number.isFinite(pe.minutes) ? pe.minutes : 18 * 60,
        kind,
        kindLabel: meta.label,
        tone: meta.tone,
        glyph: meta.glyph,
        night: true,
        venueId: pe.venueId || "personal",
        venueName: pe.venueName || "Personal",
        isPersonal: true,
        isEarmarked: earmarkedSet.has(pe.id),
        isAttention: attentionMap.has(pe.id),
        attentionReason: attentionMap.get(pe.id)?.reason || "",
        bodies: 1,
        up: 0,
        down: 0,
        score: 0,
      });
    }
  }

  // Combine and sort events
  const combinedEvents = [...filteredExistingEvents, ...personalEvents].sort(
    (a, b) => a.date.localeCompare(b.date) || a.minutes - b.minutes || a.title.localeCompare(b.title)
  );

  const eventsById = new Map(combinedEvents.map(e => [e.id, e]));

  // Recount venues excluding muted
  const venues = model.venues.filter(v => !mutedSet.has(v.id));
  const venuesById = new Map(venues.map(v => [v.id, v]));

  // Recount venue event counts
  const counts = new Map();
  for (const e of combinedEvents) counts.set(e.venueId, (counts.get(e.venueId) || 0) + 1);
  for (const v of venues) v.eventCount = counts.get(v.id) || 0;

  return {
    ...model,
    hasSteward: true,
    steward: {
      id: String(payload.stewardId || "steward"),
      name: String(payload.name || "Steward"),
      mutedCount: mutedSet.size,
      earmarkedCount: earmarkedSet.size,
      attentionCount: attentionMap.size,
      personalCount: personalEvents.length,
    },
    venues,
    venuesById,
    events: combinedEvents,
    eventsById,
  };
}

/**
 * Load steward stub or payload from environment / stub file.
 */
export async function loadStewardStub() {
  try {
    const res = await fetch("/data/steward-stub.json");
    if (res.ok) return await res.json();
  } catch {
    // fallback or offline
  }
  return null;
}
