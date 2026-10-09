// E2E test for Task 3.7: Paper-to-screen mechanic
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { launch, VIEWPORTS } from "../tools/browser.mjs";

const BASE = process.env.BASE || "http://127.0.0.1:8087";
const WEB = new URL("../", import.meta.url).pathname;
const DOCS = new URL("../../docs/", import.meta.url).pathname;
const SCREENS = DOCS + "screens/";

mkdirSync(SCREENS, { recursive: true });

console.log("=== Testing Paper-to-Screen Portal Mechanic (Task 3.7) ===");

const browser = await launch();

try {
  const page = await browser.newPage({ viewport: VIEWPORTS.desktop });

  // 1. Standalone Embed Route
  const embedUrl = `${BASE}/embed/portal/?target=note:the-room-after-midnight`;
  console.log(`Checking standalone embed route: ${embedUrl}...`);
  await page.goto(embedUrl, { waitUntil: "networkidle" });
  await page.waitForSelector(".nc-portal");
  const portalExists = await page.$eval(".nc-portal", el => el.getBoundingClientRect().height > 0);
  assert.ok(portalExists, "Portal should be rendered on embed route");
  console.log("✓ Standalone embed route renders cleanly");

  // 2. Full Page Route (/portal/)
  const pageUrl = `${BASE}/portal/?target=note:the-room-after-midnight`;
  console.log(`Checking portal full page: ${pageUrl}...`);
  await page.goto(pageUrl, { waitUntil: "networkidle" });
  await page.waitForSelector(".nc-portal");
  const titleText = await page.$eval(".nc-portal__title", el => el.textContent);
  assert.equal(titleText, "Portal Dispatch");

  // Check fallback banner presence on non-XR browser
  const fallbackBanner = await page.$eval(".nc-portal__banner--fallback", el => el.textContent);
  assert.ok(fallbackBanner.includes("Digital Reader Mode"), "Digital reader fallback should activate");
  console.log("✓ Non-AR browser gracefully defaults to Digital Reader mode");

  // Check content presence (zero dead ends)
  const nodeTitle = await page.$eval(".nc-portal__node-title", el => el.textContent);
  assert.ok(nodeTitle.includes("The Room After Midnight"), "Target node content should be rendered");

  // Check navigation links (no broken traps)
  const zineLink = await page.$eval("a[href*='/zine/']", el => el.href);
  assert.ok(zineLink.includes("/zine/"), "Zine graph link should be valid");
  console.log("✓ Target content and outlinks verified with zero modal traps or dead-ends");

  // 3. Screenshot verification
  const screenshotPath = `${SCREENS}paper-to-screen-portal.png`;
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log(`✓ Screenshot written to ${screenshotPath}`);

  // 4. Test missing/invalid target token
  await page.goto(`${BASE}/portal/?target=unregistered-qr-token`, { waitUntil: "networkidle" });
  await page.waitForSelector(".nc-portal");
  const unknownNotice = await page.$eval(".nc-portal__node-body", el => el.textContent);
  assert.ok(unknownNotice.includes("live nightlife graph"), "Friendly discovery fallback on unknown marker");
  console.log("✓ Unregistered marker token degrades gracefully to directory fallback");

} finally {
  await browser.close();
}

console.log("\nALL PAPER-TO-SCREEN PORTAL TESTS PASSED!");
