// E2E test for Task 2.4: Today page — the road timeline
// Asserts chronological DOM order, attendance box size scaling,
// tie-breaker logic, and captures screenshot.

import { writeFileSync, mkdirSync } from "node:fs";
import { launch, VIEWPORTS } from "../tools/browser.mjs";
import { sortRoadEvents } from "../components/road-timeline/road-timeline.js";
import { billboardScale } from "../components/event-card/event-card.js";

const BASE = process.env.BASE || "http://127.0.0.1:8085";
const WEB = new URL("../", import.meta.url).pathname;
const DOCS = new URL("../../docs/", import.meta.url).pathname;
const SCREENS_DOCS = DOCS + "screens/";
const SCREENS_OUTPUT = WEB + "tests/output/";

mkdirSync(SCREENS_DOCS, { recursive: true });
mkdirSync(SCREENS_OUTPUT, { recursive: true });

console.log("=== Testing Today Page — The Road Timeline (Task 2.4) ===");

// 1. Logic & Ordering Test with Seeded Events
const seededEvents = [
  {
    id: "e-late-hot",
    title: "Late Night Block Party",
    date: "2026-10-09",
    start: "10:00 PM",
    minutes: 22 * 60,
    bodies: 250,
    kind: "music",
    venueName: "The Moonlight Lounge",
    performers: ["DJ Eclipse"],
  },
  {
    id: "e-near-chill",
    title: "Acoustic Sunset Opener",
    date: "2026-10-09",
    start: "6:00 PM",
    minutes: 18 * 60,
    bodies: 5,
    kind: "music",
    venueName: "Courtyard Stage",
    performers: ["Sara Rivers"],
  },
  {
    id: "e-mid-popular",
    title: "Downtown Comedy Showcase",
    date: "2026-10-09",
    start: "8:00 PM",
    minutes: 20 * 60,
    bodies: 85,
    kind: "comedy",
    venueName: "Laughing Goat",
    performers: ["Sammy Kaye"],
  },
  {
    id: "e-mid-indie",
    title: "Indie Film & Discussion",
    date: "2026-10-09",
    start: "8:00 PM",
    minutes: 20 * 60,
    bodies: 15,
    kind: "shows",
    venueName: "Roxy Theater",
    performers: ["Local Filmmakers"],
  },
];

const sorted = sortRoadEvents(seededEvents);
const stopEventIds = sorted.map(s => s.id);
console.log("Sorted Order of Events on Road:", stopEventIds);

if (stopEventIds[0] !== "e-near-chill") {
  throw new Error(`First event must be nearest upcoming (e-near-chill), got ${stopEventIds[0]}`);
}
if (stopEventIds[1] !== "e-mid-popular") {
  throw new Error(`Second event must be e-mid-popular (8:00 PM, 85 bodies), got ${stopEventIds[1]}`);
}
if (stopEventIds[2] !== "e-mid-indie") {
  throw new Error(`Third event must be e-mid-indie (8:00 PM, 15 bodies), got ${stopEventIds[2]}`);
}
if (stopEventIds[3] !== "e-late-hot") {
  throw new Error(`Fourth event must be e-late-hot (10:00 PM), got ${stopEventIds[3]}`);
}

const scaleFirst = billboardScale(sorted[0].bodies);
const scaleLast = billboardScale(sorted[3].bodies);
console.log(`First event (nearest, 6:00 PM, 5 bodies) scale: ${scaleFirst.toFixed(3)}`);
console.log(`Fourth event (further, 10:00 PM, 250 bodies) scale: ${scaleLast.toFixed(3)}`);

if (scaleLast <= scaleFirst) {
  throw new Error(`Later-but-hotter event must have larger scale than nearest event: ${scaleLast} <= ${scaleFirst}`);
}

console.log("Mathematical & chronological ordering assertions passed.\n");

// 2. Browser Playwright E2E Verification & Screenshot
const browser = await launch();

try {
  const page = await browser.newPage({ viewport: VIEWPORTS.desktop });
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await page.waitForSelector(".nc-day-agenda");

  // Check if road timeline rendered on today page
  const pageCheck = await page.evaluate(() => {
    const road = document.querySelector(".nc-road-timeline");
    const stops = document.querySelectorAll(".nc-road__stop");
    const cards = document.querySelectorAll(".nc-road__card");
    const gauges = document.querySelectorAll(".nc-event-card__gauge");
    return {
      hasRoad: !!road,
      stopCount: stops.length,
      cardCount: cards.length,
      gaugeCount: gauges.length,
      scales: Array.from(cards).map(c => c.dataset.scale),
    };
  });

  console.log("Today page inspection:", pageCheck);

  if (!pageCheck.hasRoad) {
    throw new Error("Road timeline (.nc-road-timeline) not found on Today page (/)");
  }
  if (pageCheck.stopCount === 0) {
    throw new Error("No road stops found on today page");
  }

  // Inject seeded comparison scene to test DOM order & capture full road perspective screenshot
  const galleryPage = await browser.newPage({ viewport: { width: 1200, height: 1600 } });
  await galleryPage.goto(`${BASE}/embed/road-timeline/`, { waitUntil: "networkidle" });

  const domCheck = await galleryPage.evaluate(async (testEvents) => {
    const { roadTimeline } = await import("/components/road-timeline/road-timeline.js");
    const container = document.createElement("div");
    container.style.padding = "2.5rem";
    container.style.maxWidth = "900px";
    container.style.margin = "0 auto";

    const header = document.createElement("header");
    header.style.marginBottom = "2rem";
    header.innerHTML = `
      <h1 style="font-size: 2rem; margin-bottom: 0.5rem;">Today Page — The Road Timeline</h1>
      <p style="color: var(--nc-color-text-muted);">
        Chronological road into the distance: Position = start time (nearest first),
        Box size = expected attendance gauge. A later-but-hotter event is further down the road, yet bigger.
      </p>
    `;
    container.appendChild(header);

    const timeline = roadTimeline(testEvents, { today: "2026-10-09", level: 2 });
    container.appendChild(timeline);
    document.body.replaceChildren(container);

    const stops = Array.from(timeline.querySelectorAll(".nc-road__stop"));
    const domOrderIds = stops.map(s => s.querySelector(".nc-road__card").dataset.eventId);
    const renderedScales = stops.map(s => parseFloat(s.querySelector(".nc-road__card").dataset.scale));

    return {
      stopCount: stops.length,
      domOrderIds,
      renderedScales,
    };
  }, seededEvents);

  console.log("Seeded road DOM check:", domCheck);

  if (domCheck.domOrderIds[0] !== "e-near-chill") {
    throw new Error(`DOM order first item mismatch: expected e-near-chill, got ${domCheck.domOrderIds[0]}`);
  }
  if (domCheck.renderedScales[3] <= domCheck.renderedScales[0]) {
    throw new Error(`DOM box size mismatch: last event scale ${domCheck.renderedScales[3]} not > first event scale ${domCheck.renderedScales[0]}`);
  }

  await galleryPage.waitForTimeout(400);

  const screenPathDocs = `${SCREENS_DOCS}road-timeline-perspective.png`;
  const screenPathOut = `${SCREENS_OUTPUT}road-timeline-perspective.png`;
  await galleryPage.screenshot({ path: screenPathDocs, fullPage: true });
  await galleryPage.screenshot({ path: screenPathOut, fullPage: true });

  console.log(`Screenshot saved to:\n  ${screenPathDocs}\n  ${screenPathOut}`);
  await galleryPage.close();
  await page.close();
} finally {
  await browser.close();
}

console.log("\n=== All Road Timeline (Task 2.4) tests PASSED successfully ===");
