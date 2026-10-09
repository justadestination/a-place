// Test Suite for Task 2.7: Steward personalization hooks
// Tests: [int] feed sample payloads (empty, typical, adversarial), assert correct merge/filter/highlight.

import { applyStewardPersonalization } from "../js/data/steward.js";
import { normalize } from "../js/data/calendar.js";

console.log("=== Testing Steward Personalization Hooks (Task 2.7) ===");

// 1. Setup Base Model Fixture
const rawModel = {
  place: "Downtown Santa Rosa",
  venues: [
    { id: "v1", name: "The Mystic Lounge" },
    { id: "v2", name: "Barrel & Horn" },
    { id: "v3", name: "Arlene Francis Center" }
  ],
  events: [
    { id: "e1", title: "Public Jazz Night", date: "2026-10-15", venueId: "v1", minutes: 19 * 60, kind: "music" },
    { id: "e2", title: "Open Mic Comedy", date: "2026-10-15", venueId: "v2", minutes: 20 * 60, kind: "comedy" },
    { id: "e3", title: "Indie Rock Showcase", date: "2026-10-15", venueId: "v3", minutes: 21 * 60, kind: "music" }
  ]
};

const baseModel = normalize(rawModel);
console.log(`Base model: ${baseModel.venues.length} venues, ${baseModel.events.length} events`);

// 2. Default View (No Steward Payload)
console.log("1. Verifying default view without steward payload...");
const defaultModel = applyStewardPersonalization(baseModel, null, { enabled: false });
if (defaultModel.hasSteward) {
  throw new Error("Default view should have hasSteward=false");
}
if (defaultModel.events.length !== 3) {
  throw new Error(`Expected 3 events in default view, got ${defaultModel.events.length}`);
}
if (defaultModel.venues.length !== 3) {
  throw new Error(`Expected 3 venues in default view, got ${defaultModel.venues.length}`);
}
console.log("✓ Default view renders fully and unmodified without steward payload.");

// 3. Typical Steward Payload
console.log("2. Verifying typical steward payload behaviors (merge, mute, highlight, surface)...");
const typicalPayload = {
  stewardId: "steward-007",
  name: "Operator Test",
  personalEvents: [
    {
      id: "pe-rehearsal",
      title: "Band Rehearsal",
      date: "2026-10-15",
      minutes: 17 * 60,
      start: "5:00 PM",
      kind: "music",
      venueName: "Practice Space"
    }
  ],
  mutedVenues: ["v1"], // Hides The Mystic Lounge (e1)
  earmarkedEvents: ["e3"], // Highlights Indie Rock Showcase
  broughtToAttention: [
    {
      id: "bta-1",
      eventId: "e2",
      reason: "Recommended by local music cohort"
    }
  ]
};

const personalized = applyStewardPersonalization(baseModel, typicalPayload, { enabled: true });

// Behavior 1: Merges personal calendar
const personalEvent = personalized.events.find(e => e.id === "pe-rehearsal");
if (!personalEvent) {
  throw new Error("Personal calendar event was not merged into events!");
}
if (!personalEvent.isPersonal) {
  throw new Error("Personal event should have isPersonal=true flag");
}
// Chronological sort check: 17:00 (5PM) should come first before 20:00 and 21:00
if (personalized.events[0].id !== "pe-rehearsal") {
  throw new Error(`Personal event at 17:00 should sort first, got ${personalized.events[0].id}`);
}
console.log("✓ Behavior 1: Personal calendar successfully merged and chronologically sorted.");

// Behavior 2: Hides muted venues
const mutedEvent = personalized.events.find(e => e.venueId === "v1");
if (mutedEvent) {
  throw new Error(`Muted venue v1 event was not hidden! Found: ${mutedEvent.id}`);
}
const mutedVenueInList = personalized.venues.find(v => v.id === "v1");
if (mutedVenueInList) {
  throw new Error(`Muted venue v1 was not removed from venues list!`);
}
console.log("✓ Behavior 2: Muted venue (v1) and its events successfully hidden.");

// Behavior 3: Highlights earmarked events
const earmarkedEvent = personalized.events.find(e => e.id === "e3");
if (!earmarkedEvent || !earmarkedEvent.isEarmarked) {
  throw new Error("Earmarked event e3 does not have isEarmarked=true flag!");
}
console.log("✓ Behavior 3: Earmarked event (e3) successfully highlighted.");

// Behavior 4: Surfaces brought-to-attention items
const attentionEvent = personalized.events.find(e => e.id === "e2");
if (!attentionEvent || !attentionEvent.isAttention) {
  throw new Error("Brought-to-attention event e2 does not have isAttention=true flag!");
}
if (!attentionEvent.attentionReason.includes("Recommended")) {
  throw new Error(`Expected attention reason, got: ${attentionEvent.attentionReason}`);
}
console.log("✓ Behavior 4: Brought-to-attention item (e2) successfully surfaced.");

// 4. Empty Payload
console.log("3. Verifying empty steward payload ({}) degradation...");
const emptyResult = applyStewardPersonalization(baseModel, {}, { enabled: true });
if (emptyResult.events.length !== 3) {
  throw new Error(`Empty payload should preserve all 3 events, got ${emptyResult.events.length}`);
}
if (emptyResult.events.some(e => e.isPersonal || e.isEarmarked || e.isAttention)) {
  throw new Error("Empty payload should not flag any events as personal/earmarked/attention");
}
console.log("✓ Empty payload degrades cleanly without errors.");

// 5. Adversarial Payloads
console.log("4. Verifying adversarial steward payload defenses...");
const adversarialPayloads = [
  null,
  undefined,
  "invalid-string-payload",
  12345,
  {
    mutedVenues: "not-an-array",
    earmarkedEvents: 999,
    broughtToAttention: "invalid",
    personalEvents: [null, undefined, "bad", { id: "", date: 123 }]
  },
  {
    mutedVenues: [null, {}],
    earmarkedEvents: [null],
    broughtToAttention: [null, { eventId: 123 }, { notEventId: "x" }],
    personalEvents: [{ id: "bad-date-missing" }]
  }
];

for (let i = 0; i < adversarialPayloads.length; i++) {
  try {
    const advResult = applyStewardPersonalization(baseModel, adversarialPayloads[i], { enabled: true });
    if (!advResult || !Array.isArray(advResult.events)) {
      throw new Error(`Adversarial payload ${i} broke model structure`);
    }
  } catch (err) {
    throw new Error(`Adversarial payload ${i} crashed with exception: ${err.message}`);
  }
}
console.log(`✓ All ${adversarialPayloads.length} adversarial payloads safely handled.`);

console.log("\n✓ All Task 2.7 Steward personalization tests passed successfully!");
