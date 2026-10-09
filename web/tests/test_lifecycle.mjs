import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { launch, VIEWPORTS } from "../tools/browser.mjs";
import { computeLifecycle, expandRecurringEvents } from "../js/data/lifecycle.js";

const require = createRequire(import.meta.url);
const AXE = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.env.BASE || "http://127.0.0.1:8088";
const DOCS = new URL("../../docs/", import.meta.url).pathname;

console.log("=== Testing Event Lifecycle & Recurrence (Task 2.9) ===");

// 1. Test multi-week recurrence expansion logic
const sampleRecurringEvent = {
  id: "thursday-jazz-residency",
  title: "Weekly Thursday Jazz Jam",
  date: "2026-10-08",
  startsAt: "2026-10-08T20:00:00-07:00",
  endsAt: "2026-10-08T23:00:00-07:00",
  venue: "Arlene Francis Center",
  venueId: "afc",
  kind: "music",
  isRecurring: true,
  recurrence: "weekly",
  performers: ["Downtown Trio"],
  bodies: 120,
};

const expanded = expandRecurringEvents([sampleRecurringEvent], "2026-10-08", "2026-10-25");
if (expanded.length !== 3) {
  throw new Error(`Expected 3 weekly occurrences across 3 weeks, got ${expanded.length}`);
}
console.log(`✓ Multi-week recurring event expanded to ${expanded.length} weekly occurrences: ${expanded.map(e => e.date).join(", ")}`);

// 2. Test lifecycle state computation
const freezeNow = new Date("2026-10-08T21:00:00-07:00");
const lc = computeLifecycle("2026-10-08T20:00:00-07:00", "2026-10-08T23:00:00-07:00", freezeNow);
if (lc.state !== "happening_now" || !lc.happeningNow) {
  throw new Error(`Expected state happening_now, got ${JSON.stringify(lc)}`);
}
console.log("✓ Clock freeze transition verified: happening_now state active during show");

// 3. Browser test: render eventCard with happening-now and recurring badges
const browser = await launch();

try {
  const page = await browser.newPage({
    viewport: { width: 390, height: 844 },
    colorScheme: "dark",
    bypassCSP: true,
  });

  await page.goto(`${BASE}/embed/event-card/`, { waitUntil: "networkidle" });
  await page.waitForTimeout(200);

  // Inject a live rendering of the happening-now event card
  await page.evaluate(async () => {
    const { eventCard } = await import("/components/event-card/event-card.js");
    const container = document.getElementById("app");
    const liveEvent = {
      id: "live-show-now",
      title: "Midnight Neo-Soul Jam",
      date: "2026-10-09",
      start: "8:00 pm",
      end: "11:00 pm",
      startsAt: "2026-10-09T20:00:00-07:00",
      endsAt: "2026-10-09T23:00:00-07:00",
      venueName: "Mystic Theater",
      kind: "music",
      performers: ["Soul Collective"],
      bodies: 240,
      checks: [],
      happeningNow: true,
      lifecycle: "happening_now",
      isRecurring: true,
    };
    const card = eventCard(liveEvent, { level: 2 });
    container.replaceChildren(card);
  });
  await page.waitForTimeout(100);

  // Assert badges present in DOM
  const nowBadge = await page.$(".nc-badge--happening-now");
  const recurringBadge = await page.$(".nc-badge--recurring");

  if (!nowBadge) throw new Error("Happening now badge not found in DOM");
  if (!recurringBadge) throw new Error("Weekly residency badge not found in DOM");

  const badgeText = await page.evaluate(el => el.textContent.trim(), nowBadge);
  if (!badgeText.includes("Happening now")) {
    throw new Error(`Unexpected badge text: ${badgeText}`);
  }

  // Axe accessibility audit
  await page.addScriptTag({ content: AXE });
  const axeResult = await page.evaluate(async () => {
    return await window.axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] },
      rules: { region: { enabled: false } },
    });
  });

  if (axeResult.violations.length > 0) {
    console.error("Axe violations:", axeResult.violations.map(v => v.id));
    throw new Error(`Axe violations on event-card: ${axeResult.violations[0].id}`);
  }

  // Capture screenshot
  const screenPath = DOCS + "screens/event-lifecycle-states.png";
  await page.screenshot({ path: screenPath });
  console.log(`✓ Screenshot captured at ${screenPath}`);

  await page.close();
} finally {
  await browser.close();
}

console.log("✓ Task 2.9 (Event lifecycle) passed all lifecycle, recurrence, and accessibility tests");
