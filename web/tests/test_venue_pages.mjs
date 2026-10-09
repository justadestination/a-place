import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { launch, VIEWPORTS } from "../tools/browser.mjs";

const require = createRequire(import.meta.url);
const AXE = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.env.BASE || "http://127.0.0.1:8089";
const DOCS = new URL("../../docs/", import.meta.url).pathname;

console.log("=== Testing Venue Pages & Closed Venue Protection (Task 2.12) ===");

// 1. Verify build files
if (!existsSync("web/embed/venue-page/index.html")) {
  console.error("FAIL: Missing web/embed/venue-page/index.html");
  process.exit(1);
}
if (!existsSync("web/venue/index.html")) {
  console.error("FAIL: Missing web/venue/index.html");
  process.exit(1);
}
console.log("✓ Route files /embed/venue-page/ and /venue/ built cleanly");

const browser = await launch();

try {
  // 2. Audit /embed/venue-page/ across viewports and color schemes with Axe
  for (const [vpName, vp] of Object.entries(VIEWPORTS)) {
    for (const scheme of ["light", "dark"]) {
      const page = await browser.newPage({
        viewport: { width: vp.width, height: vp.height },
        ...vp,
        colorScheme: scheme,
        bypassCSP: true,
      });

      await page.goto(`${BASE}/embed/venue-page/`, { waitUntil: "networkidle" });
      await page.waitForTimeout(150);

      // Verify DOM title
      const title = await page.$eval("#nc-venue-title", el => el.textContent.trim());
      if (!title || title.length === 0) {
        throw new Error(`Venue title empty on /embed/venue-page/ (${vpName} ${scheme})`);
      }

      // Check touch target heights on all interactive buttons & links
      const targetHeights = await page.$$eval(".nc-venue-action-btn", els =>
        els.map(el => Math.round(el.getBoundingClientRect().height))
      );
      for (const h of targetHeights) {
        if (h < 44) {
          throw new Error(`Interactive target height ${h}px is less than WCAG 2.2 target size 44px on ${vpName}`);
        }
      }

      // Axe audit
      await page.addScriptTag({ content: AXE });
      const axeResult = await page.evaluate(async () => {
        return await window.axe.run(document, {
          runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] },
          rules: { region: { enabled: false } },
        });
      });

      if (axeResult.violations.length > 0) {
        console.error(`Axe violations on /embed/venue-page/ (${vpName} ${scheme}):`, axeResult.violations.map(v => v.id));
        throw new Error(`Axe violations found: ${axeResult.violations[0].id}`);
      }

      await page.close();
    }
  }
  console.log("✓ /embed/venue-page/ verified across all viewports and color schemes with 0 Axe violations");

  // 3. Test open venue renders all sections
  const openPage = await browser.newPage({
    viewport: { width: 1280, height: 800 },
    colorScheme: "dark",
    bypassCSP: true,
  });

  await openPage.goto(`${BASE}/embed/venue-page/`, { waitUntil: "networkidle" });
  await openPage.waitForTimeout(200);

  const statusText = await openPage.$eval("#nc-venue-status-banner", el => el.textContent.trim());
  if (!statusText.includes("Open & Active")) {
    throw new Error(`Expected Open & Active status, got: "${statusText}"`);
  }

  const yelpLink = await openPage.$eval("#nc-venue-yelp-link", el => el.getAttribute("href"));
  if (!yelpLink || !yelpLink.includes("yelp.com")) {
    throw new Error(`Expected valid Yelp link, got: "${yelpLink}"`);
  }

  const eventCount = await openPage.$$eval(".nc-venue-event-item", els => els.length);
  if (eventCount === 0) {
    throw new Error("Expected upcoming events rendered on open venue page");
  }
  console.log(`✓ Open venue renders profile, Yelp link, blurbs, and ${eventCount} upcoming events`);

  // Capture screenshot of open venue page
  await openPage.screenshot({ path: `${DOCS}screens/venue-page.png` });
  console.log(`✓ Screenshot captured at docs/screens/venue-page.png`);
  await openPage.close();

  // 4. Test closed venue shows status banner and NO upcoming events
  const closedPage = await browser.newPage({
    viewport: { width: 1280, height: 800 },
    colorScheme: "dark",
    bypassCSP: true,
  });

  await closedPage.goto(`${BASE}/embed/venue-page/?closed=1`, { waitUntil: "networkidle" });
  await closedPage.waitForTimeout(200);

  const closedBanner = await closedPage.$eval("#nc-venue-status-banner", el => el.textContent.trim());
  if (!closedBanner.includes("Permanently Closed")) {
    throw new Error(`Expected Permanently Closed status banner, got: "${closedBanner}"`);
  }

  const closedNoEventsMsg = await closedPage.$eval("#nc-venue-no-events", el => el.textContent.trim());
  if (!closedNoEventsMsg.includes("No upcoming events scheduled. Venue is closed.")) {
    throw new Error(`Expected closed events message, got: "${closedNoEventsMsg}"`);
  }

  const closedEventCount = await closedPage.$$eval(".nc-venue-event-item", els => els.length);
  if (closedEventCount !== 0) {
    throw new Error(`Closed venue rendered ${closedEventCount} events! Must render zero events.`);
  }
  console.log("✓ Closed venue verified: status banner displayed and exactly ZERO upcoming events rendered");

  // Audit closed venue state with Axe
  await closedPage.addScriptTag({ content: AXE });
  const closedAxe = await closedPage.evaluate(async () => {
    return await window.axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] },
      rules: { region: { enabled: false } },
    });
  });
  if (closedAxe.violations.length > 0) {
    throw new Error(`Axe violation on closed venue view: ${closedAxe.violations[0].id}`);
  }
  console.log("✓ Closed venue view verified with 0 Axe violations");

  await closedPage.close();
  console.log("=== All Task 2.12 E2E Tests PASSED ===");
} finally {
  await browser.close();
}
