import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { launch, VIEWPORTS } from "../tools/browser.mjs";
import { normalize } from "../js/data/calendar.js";
import { formatLocalizedTime, getTimezoneAbbr, formatTimeRange } from "../js/data/tz.js";

const require = createRequire(import.meta.url);
const AXE = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.env.BASE || "http://127.0.0.1:8089";
const DOCS = new URL("../../docs/", import.meta.url).pathname;

console.log("=== Testing Timezone Correctness & Multi-Region Support (Task 2.10) ===");

// 1. Data model & normalization multi-timezone verification
const sampleData = {
  place: "Multi-Region Network",
  venues: [
    {
      id: "ven_sr_cali",
      name: "California Theater",
      address: "528 7th St, Santa Rosa, CA",
      timezone: "America/Los_Angeles",
    },
    {
      id: "ven_ny_brooklyn",
      name: "Brooklyn Bowl",
      address: "61 Wythe Ave, Brooklyn, NY",
      timezone: "America/New_York",
    },
  ],
  events: [
    {
      id: "ev_west_coast",
      venueId: "ven_sr_cali",
      title: "Pacific Coast Sunset Sessions",
      kind: "music",
      date: "2026-10-08",
      startsAt: "2026-10-09T03:00:00Z", // 8:00 pm PDT
      endsAt: "2026-10-09T06:00:00Z",   // 11:00 pm PDT
    },
    {
      id: "ev_east_coast",
      venueId: "ven_ny_brooklyn",
      title: "Atlantic Midnight Groove",
      kind: "music",
      date: "2026-10-08",
      startsAt: "2026-10-09T00:00:00Z", // 8:00 pm EDT
      endsAt: "2026-10-09T03:00:00Z",   // 11:00 pm EDT
    },
  ],
};

const model = normalize(sampleData);
const evWest = model.eventsById.get("ev_west_coast");
const evEast = model.eventsById.get("ev_east_coast");

if (!evWest || !evEast) {
  throw new Error("Failed to normalize test events across timezones");
}

console.log(`West Coast event: timezone=${evWest.timezone}, abbr=${evWest.tzAbbr}, start=${evWest.localizedStart}`);
console.log(`East Coast event: timezone=${evEast.timezone}, abbr=${evEast.tzAbbr}, start=${evEast.localizedStart}`);

if (evWest.tzAbbr !== "PDT" || !evWest.localizedStart.includes("PDT")) {
  throw new Error(`West Coast event expected PDT, got: ${evWest.localizedStart}`);
}
if (evEast.tzAbbr !== "EDT" || !evEast.localizedStart.includes("EDT")) {
  throw new Error(`East Coast event expected EDT, got: ${evEast.localizedStart}`);
}
console.log("✓ Multi-timezone data normalization verified (PDT vs EDT)");

// 2. Browser rendering & accessibility audit
const browser = await launch();

try {
  const page = await browser.newPage({
    viewport: { width: 390, height: 844 },
    colorScheme: "dark",
    bypassCSP: true,
  });

  // Navigate to embed route and render both cards
  await page.goto(`${BASE}/embed/event-card/`, { waitUntil: "networkidle" });
  await page.waitForTimeout(200);

  // Evaluate rendering in page context using eventCard
  const renderedCheck = await page.evaluate(async (testData) => {
    const [{ normalize }, { eventCard }] = await Promise.all([
      import("/js/data/calendar.js"),
      import("/components/event-card/event-card.js"),
    ]);


    const m = normalize(testData);
    const wEvent = m.eventsById.get("ev_west_coast");
    const eEvent = m.eventsById.get("ev_east_coast");
    const wVenue = m.venuesById.get(wEvent.venueId);
    const eVenue = m.venuesById.get(eEvent.venueId);

    const cardWest = eventCard(wEvent, { venue: wVenue });
    const cardEast = eventCard(eEvent, { venue: eVenue });

    const root = document.getElementById("app");
    root.innerHTML = "";
    root.append(cardWest, cardEast);

    return {
      westText: cardWest.textContent,
      eastText: cardEast.textContent,
    };
  }, sampleData);

  if (!renderedCheck.westText.includes("PDT")) {
    throw new Error(`West Coast card missing PDT abbreviation in rendered DOM: ${renderedCheck.westText}`);
  }
  if (!renderedCheck.eastText.includes("EDT")) {
    throw new Error(`East Coast card missing EDT abbreviation in rendered DOM: ${renderedCheck.eastText}`);
  }
  console.log("✓ Both timezone cards rendered localized times with abbreviations (PDT and EDT)");

  // Axe accessibility audit
  await page.addScriptTag({ content: AXE });
  const axeResult = await page.evaluate(async () => {
    return await window.axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] },
      rules: { region: { enabled: false } },
    });
  });

  if (axeResult.violations.length > 0) {
    console.error("Axe violations on multi-timezone render:", axeResult.violations.map(v => v.id));
    throw new Error(`Axe violations found: ${axeResult.violations[0].id}`);
  }
  console.log("✓ Multi-timezone render verified with 0 Axe violations");

  // Capture screenshot
  const screenPath = DOCS + "screens/multi-timezone-venues.png";
  await page.screenshot({ path: screenPath });
  console.log(`✓ Screenshot captured at ${screenPath}`);

  await page.close();
} finally {
  await browser.close();
}

console.log("✓ Task 2.10 (Timezone correctness) passed all unit, normalization, and browser checks");
