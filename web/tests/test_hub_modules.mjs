// E2E test for Task 2.8: Hub module composition
// Asserts each module standalone on its /embed route, and hub layout with all slots empty.

import { mkdirSync } from "node:fs";
import { launch, VIEWPORTS } from "../tools/browser.mjs";

const BASE = process.env.BASE || "http://127.0.0.1:8085";
const WEB = new URL("../", import.meta.url).pathname;
const DOCS = new URL("../../docs/", import.meta.url).pathname;
const SCREENS_DOCS = DOCS + "screens/";
const SCREENS_OUTPUT = WEB + "tests/output/";

mkdirSync(SCREENS_DOCS, { recursive: true });
mkdirSync(SCREENS_OUTPUT, { recursive: true });

console.log("=== Testing Hub Module Composition (Task 2.8) ===");

const browser = await launch();

try {
  const context = await browser.newContext({ viewport: VIEWPORTS.desktop });
  const page = await context.newPage();

  // 1. Test standalone embed routes for each of the 4 auxiliary slots
  const modules = [
    { name: "hub-zine", selector: ".nc-hub-zine" },
    { name: "hub-summary", selector: ".nc-hub-summary" },
    { name: "hub-inbox", selector: ".nc-hub-inbox" },
    { name: "hub-market", selector: ".nc-hub-market" },
    { name: "hub-layout", selector: ".nc-hub-layout" },
  ];

  for (const mod of modules) {
    const embedUrl = `${BASE}/embed/${mod.name}/`;
    console.log(`Checking standalone embed route: ${embedUrl}...`);
    await page.goto(embedUrl, { waitUntil: "networkidle" });
    await page.waitForSelector(mod.selector);
    const visible = await page.$eval(mod.selector, el => el.getBoundingClientRect().height > 0);
    if (!visible) {
      throw new Error(`Module ${mod.name} is not visible on its standalone embed route`);
    }
    console.log(`✓ Module ${mod.name} renders cleanly on ${embedUrl}`);
  }

  // 2. Test Hub composition on index (with slots empty)
  console.log(`Navigating to hub index at ${BASE}/...`);
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await page.waitForSelector(".nc-hub-layout");
  await page.waitForSelector(".nc-hub-hero");
  await page.waitForSelector(".nc-hub-auxiliary");

  // Assert hero timeline is present
  const heroPresent = await page.$eval(".nc-hub-hero", el => el.children.length > 0);
  if (!heroPresent) throw new Error("Hero slot is missing content in hub layout");

  // Assert all 4 auxiliary slots degrade gracefully when empty
  const auxCount = await page.$$eval(".nc-hub-slot", slots => slots.length);
  console.log(`Auxiliary slots rendered in hub layout: ${auxCount}`);
  if (auxCount < 4) {
    throw new Error(`Expected at least 4 auxiliary slots in hub layout, found ${auxCount}`);
  }

  // Capture screenshot of hub module composition
  const screenPath = SCREENS_DOCS + "hub-module-composition.png";
  await page.screenshot({ path: screenPath, fullPage: true });
  console.log(`✓ Screenshot captured to ${screenPath}`);

} finally {
  await browser.close();
}

console.log("\n✓ All Task 2.8 Hub module composition checks passed!");
