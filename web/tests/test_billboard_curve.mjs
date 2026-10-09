// E2E test for Task 2.2 / Decision 005: Billboard event card sizing curve
// Tests synthetic tallies from 0 to 10,000, asserts legibility and bounds,
// and captures screenshots of the curve progression.

import { writeFileSync, mkdirSync } from "node:fs";
import { launch, VIEWPORTS } from "../tools/browser.mjs";
import { billboardScale } from "../components/event-card/event-card.js";

const BASE = process.env.BASE || "http://127.0.0.1:8085";
const WEB = new URL("../", import.meta.url).pathname;
const DOCS = new URL("../../docs/", import.meta.url).pathname;
const SCREENS_DOCS = DOCS + "screens/";
const SCREENS_OUTPUT = WEB + "tests/output/";

mkdirSync(SCREENS_DOCS, { recursive: true });
mkdirSync(SCREENS_OUTPUT, { recursive: true });

const TALLIES = [0, 1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000];

console.log("=== Testing Billboard Sizing Curve (Decision 005) ===");
console.log("Formula: size = clamp(min_size + k * ln(1 + max(0, bodies)), min_size, max_size)");
console.log("Params: min_size = 1.0, k = 0.082, max_size = 1.75\n");

// 1. Math verification across the entire domain [0, 10000]
let prevScale = 0;
for (const bodies of TALLIES) {
  const scale = billboardScale(bodies);
  console.log(`  bodies: ${String(bodies).padStart(5)} -> scale: ${scale.toFixed(4)}`);
  
  if (scale < 1.0) {
    throw new Error(`Scale below min_size for ${bodies}: ${scale}`);
  }
  if (scale > 1.75) {
    throw new Error(`Scale above max_size for ${bodies}: ${scale}`);
  }
  if (scale < prevScale) {
    throw new Error(`Scale not monotonic at ${bodies}: ${scale} < ${prevScale}`);
  }
  prevScale = scale;
}

// Low-to-medium turnout differentiation check (5 vs 25 attendees)
const scale5 = billboardScale(5);
const scale25 = billboardScale(25);
if (scale25 - scale5 < 0.1) {
  throw new Error(`Insufficient differentiation between 5 (${scale5}) and 25 (${scale25}) bodies`);
}

// Bounded ceiling check for runaway popular event
const scale10k = billboardScale(10000);
if (scale10k !== 1.75) {
  throw new Error(`10,000 bodies must clamp at max_size (1.75), got ${scale10k}`);
}

console.log("\nMathematical curve verification passed.\n");

// 2. Launch browser and verify rendered DOM & visual scaling
const browser = await launch();

try {
  // A. Verify individual embed rendering across tallies
  for (const bodies of [0, 5, 25, 100, 1000, 10000]) {
    const page = await browser.newPage({ viewport: VIEWPORTS.desktop });
    const url = `${BASE}/embed/event-card/?bodies=${bodies}`;
    await page.goto(url, { waitUntil: "networkidle" });
    await page.waitForSelector(".nc-event-card");

    const data = await page.evaluate(() => {
      const card = document.querySelector(".nc-event-card");
      const title = document.querySelector(".nc-event-card__title");
      const gauge = document.querySelector(".nc-event-card__gauge");
      const rect = card.getBoundingClientRect();
      const style = getComputedStyle(card);
      const titleStyle = getComputedStyle(title);
      return {
        bodies: card.dataset.bodies,
        scale: card.dataset.scale,
        cardScaleProp: style.getPropertyValue("--nc-card-scale").trim(),
        width: rect.width,
        height: rect.height,
        titleFontSize: parseFloat(titleStyle.fontSize),
        gaugeText: gauge?.textContent?.trim() || "",
        hScroll: document.documentElement.scrollWidth > window.innerWidth,
      };
    });

    console.log(`Rendered embed for ${bodies} bodies: scale=${data.scale}, height=${Math.round(data.height)}px, titleSize=${data.titleFontSize}px, gauge="${data.gaugeText}"`);

    if (data.hScroll) {
      throw new Error(`Horizontal scroll detected at bodies=${bodies}! Card broke layout.`);
    }
    if (bodies === 0 && data.titleFontSize < 20) {
      throw new Error(`Smallest card illegible: title font size ${data.titleFontSize}px < 20px`);
    }
    if (bodies === 10000 && data.height > 1200) {
      throw new Error(`Largest card swallowed the page: height ${data.height}px > 1200px`);
    }

    await page.close();
  }

  // B. Render comparison gallery showing the full curve side by side
  // Build a test gallery page
  const galleryPage = await browser.newPage({ viewport: { width: 1440, height: 1800 } });
  
  // Navigate to embed with gallery injected
  await galleryPage.goto(`${BASE}/embed/event-card/`, { waitUntil: "networkidle" });
  await galleryPage.evaluate(async (testTallies) => {
    const { eventCard } = await import("/components/event-card/event-card.js");
    const { loadCalendar } = await import("/js/data/calendar.js");
    const model = await loadCalendar();
    const baseEvent = model.events[0] || {
      id: "test-event",
      title: "The Lost Church Downtown Revue",
      date: "2026-10-09",
      start: "8:00 PM",
      end: "11:00 PM",
      kind: "music",
      venueName: "The Lost Church Santa Rosa",
      venueId: "lost-church",
      performers: ["The Twilight Singers", "Downtown Brass"],
      checks: [{ name: "The Lost Church", url: "https://thelostchurch.org" }],
    };

    const container = document.createElement("div");
    container.id = "curve-gallery";
    container.style.padding = "2rem";
    container.style.display = "grid";
    container.style.gap = "2.5rem";
    container.style.maxWidth = "1100px";
    container.style.margin = "0 auto";

    const header = document.createElement("header");
    header.innerHTML = `
      <h1 style="font-size: 2rem; margin-bottom: 0.5rem;">Billboard Sizing Curve Verification</h1>
      <p style="color: var(--nc-color-text-muted); margin-bottom: 2rem;">
        Decision 005 logarithmic scale from 0 to 10,000 synthetic attendance tallies.
        Baseline 1.0 (legible base), logarithmic growth across 5 to 500, clamped at 1.75 ceiling.
      </p>
    `;
    container.appendChild(header);

    for (const count of testTallies) {
      const section = document.createElement("section");
      section.style.display = "grid";
      section.style.gap = "0.75rem";
      
      const label = document.createElement("div");
      label.style.fontWeight = "bold";
      label.style.color = "var(--nc-color-accent-text)";
      label.textContent = `Turnout Tally: ${count.toLocaleString()} bodies`;
      section.appendChild(label);

      const ev = { ...baseEvent, id: `test-event-${count}`, bodies: count, up: count };
      const card = eventCard(ev, { today: "2026-10-09", showImage: false });
      section.appendChild(card);
      container.appendChild(section);
    }

    document.body.replaceChildren(container);
  }, [0, 5, 25, 100, 500, 10000]);

  await galleryPage.waitForTimeout(500);

  // Capture full curve screenshot
  const screenshotPathDocs = `${SCREENS_DOCS}billboard-curve-scale.png`;
  const screenshotPathOut = `${SCREENS_OUTPUT}billboard-curve-0-to-10000.png`;
  await galleryPage.screenshot({ path: screenshotPathDocs, fullPage: true });
  await galleryPage.screenshot({ path: screenshotPathOut, fullPage: true });

  console.log(`\nScreenshots saved to:`);
  console.log(`  ${screenshotPathDocs}`);
  console.log(`  ${screenshotPathOut}`);

  await galleryPage.close();
} finally {
  await browser.close();
}

console.log("\n=== All Billboard Sizing Curve tests PASSED successfully ===");
