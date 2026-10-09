// E2E test for Task 2.5: Filters (tags, venues)
// Asserts filter controls update URL parameters, and loading the URL
// in a fresh session reproduces the exact filtered view.

import { writeFileSync, mkdirSync } from "node:fs";
import { launch, VIEWPORTS } from "../tools/browser.mjs";
import { loadCalendar, filterEvents, roomsWithEvents, kindsWithEvents } from "../js/data/calendar.js";

const BASE = process.env.BASE || "http://127.0.0.1:8085";
const WEB = new URL("../", import.meta.url).pathname;
const DOCS = new URL("../../docs/", import.meta.url).pathname;
const SCREENS_DOCS = DOCS + "screens/";
const SCREENS_OUTPUT = WEB + "tests/output/";

mkdirSync(SCREENS_DOCS, { recursive: true });
mkdirSync(SCREENS_OUTPUT, { recursive: true });

console.log("=== Testing Filters: Tags & Venues (Task 2.5) ===");

// 1. Data Model Verification
const model = await loadCalendar({ api: `${BASE}/api/model` });
console.log(`Loaded calendar: ${model.venues.length} venues, ${model.events.length} events`);

const allEvents = filterEvents(model, { scope: "all" });
const nightEvents = filterEvents(model, { scope: "nights" });
console.log(`Events: all=${allEvents.length}, nights=${nightEvents.length}`);

// Test filtering by kind/tag
const musicEvents = filterEvents(model, { scope: "all", kind: "music" });
for (const e of musicEvents) {
  if (e.kind !== "music") {
    throw new Error(`Non-music event returned with kind='music': ${e.id} (${e.kind})`);
  }
}
console.log(`Filtered kind='music': ${musicEvents.length} events`);

// Test filtering by venue
const musicEvent = model.events.find(e => e.kind === "music");
const targetVenue = model.venuesById.get(musicEvent.venueId);
const venueEvents = filterEvents(model, { scope: "all", venueId: targetVenue.id });
for (const e of venueEvents) {
  if (e.venueId !== targetVenue.id) {
    throw new Error(`Non-matching venue returned: ${e.id} (${e.venueId} !== ${targetVenue.id})`);
  }
}
console.log(`Filtered venue='${targetVenue.name}': ${venueEvents.length} events`);

// 2. Playwright E2E: Apply Filters, Check URL, and Verify Fresh Session Reproduction
const browser = await launch();

try {
  const contextA = await browser.newContext({ viewport: VIEWPORTS.desktop });
  const pageA = await contextA.newPage();

  console.log("Session A: Navigating to index...");
  await pageA.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await pageA.waitForSelector(".nc-filters");

  // Select venue and kind
  const targetVenueId = targetVenue.id;
  console.log(`Session A: Selecting venue=${targetVenueId} and tag=music...`);

  await pageA.selectOption(".nc-filters__room select", targetVenueId);
  await pageA.selectOption(".nc-filters__kind select", "music");

  // Wait for URL params to sync
  await pageA.waitForTimeout(300);
  const currentUrl = pageA.url();
  console.log("Session A updated URL:", currentUrl);

  const urlObj = new URL(currentUrl);
  if (urlObj.searchParams.get("venue") !== targetVenueId) {
    throw new Error(`Expected ?venue=${targetVenueId} in URL, got ${urlObj.searchParams.get("venue")}`);
  }
  if (urlObj.searchParams.get("kind") !== "music") {
    throw new Error(`Expected ?kind=music in URL, got ${urlObj.searchParams.get("kind")}`);
  }

  // Count events in Session A
  const eventsCountA = await pageA.evaluate(() => {
    return document.querySelectorAll(".nc-road__card, .nc-event-row").length;
  });
  console.log(`Session A rendered events count: ${eventsCountA}`);

  // 3. Fresh Session B: Open copied URL in clean context
  console.log("Session B: Opening copied URL in a fresh session...");
  const contextB = await browser.newContext({ viewport: VIEWPORTS.desktop });
  const pageB = await contextB.newPage();
  await pageB.goto(currentUrl, { waitUntil: "networkidle" });
  await pageB.waitForSelector(".nc-filters");

  const stateB = await pageB.evaluate(() => {
    const roomSelect = document.querySelector(".nc-filters__room select");
    const kindSelect = document.querySelector(".nc-filters__kind select");
    const cards = Array.from(document.querySelectorAll(".nc-road__card, .nc-event-row"));
    return {
      selectedVenue: roomSelect?.value,
      selectedKind: kindSelect?.value,
      eventCount: cards.length,
      eventIds: cards.map(c => c.dataset.eventId || c.getAttribute("data-event-id")),
    };
  });

  console.log("Session B state:", stateB);

  if (stateB.selectedVenue !== targetVenueId) {
    throw new Error(`Session B selected venue mismatch: ${stateB.selectedVenue} !== ${targetVenueId}`);
  }
  if (stateB.selectedKind !== "music") {
    throw new Error(`Session B selected kind mismatch: ${stateB.selectedKind} !== 'music'`);
  }
  if (stateB.eventCount !== eventsCountA) {
    throw new Error(`Session B event count (${stateB.eventCount}) does not match Session A (${eventsCountA})`);
  }

  // 4. Test embed route with URL params
  console.log("Testing embed route with URL params...");
  const embedPage = await browser.newPage({ viewport: VIEWPORTS.desktop });
  await embedPage.goto(`${BASE}/embed/filter-bar/?venue=${targetVenueId}&kind=music`, { waitUntil: "networkidle" });
  const embedState = await embedPage.evaluate(() => {
    const roomSelect = document.querySelector(".nc-filters__room select");
    const kindSelect = document.querySelector(".nc-filters__kind select");
    return {
      selectedVenue: roomSelect?.value,
      selectedKind: kindSelect?.value,
    };
  });
  console.log("Embed filter-bar state:", embedState);

  if (embedState.selectedVenue !== targetVenueId || embedState.selectedKind !== "music") {
    throw new Error(`Embed route filter mismatch: ${JSON.stringify(embedState)}`);
  }

  // Capture screenshot of filtered view
  const screenPathDocs = `${SCREENS_DOCS}filters-applied-shareable-url.png`;
  const screenPathOut = `${SCREENS_OUTPUT}filters-applied-shareable-url.png`;
  await pageB.screenshot({ path: screenPathDocs, fullPage: true });
  await pageB.screenshot({ path: screenPathOut, fullPage: true });

  console.log(`Screenshot saved to:\n  ${screenPathDocs}\n  ${screenPathOut}`);

  await pageA.close();
  await contextA.close();
  await pageB.close();
  await contextB.close();
  await embedPage.close();
} finally {
  await browser.close();
}

console.log("\n=== All Filter (Task 2.5) tests PASSED successfully ===");
