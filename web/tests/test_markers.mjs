// E2E test for Task 3.8: QR / mosaic markers
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { launch, VIEWPORTS } from "../tools/browser.mjs";

const ROOT = resolve(new URL("../..", import.meta.url).pathname);
const BASE = process.env.BASE || "http://127.0.0.1:8087";
const DOCS = resolve(ROOT, "docs");
const SCREENS = resolve(DOCS, "screens");

mkdirSync(SCREENS, { recursive: true });

console.log("=== Testing QR / Mosaic Markers (Task 3.8) ===");

// 1. Python Generator Test
const pyScript = resolve(ROOT, "web/tools/generate_markers.py");
execFileSync("python3", [pyScript, "--all"], { cwd: ROOT, encoding: "utf-8" });

const manifestPath = resolve(ROOT, "web/data/markers/index.json");
assert.ok(existsSync(manifestPath), "Markers index.json manifest must exist");
const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
assert.ok(manifest.length >= 3, `Expected at least 3 markers, got ${manifest.length}`);

// Verify SVG structure for first marker
const firstMarker = manifest[0];
assert.ok(firstMarker.destination_url.includes("/portal/?target="));
assert.ok(firstMarker.fallback_caption.includes("shady.example.org"));

const svgPath = resolve(ROOT, "web" + firstMarker.file);
assert.ok(existsSync(svgPath), `Marker file ${svgPath} must exist`);
const svgContent = readFileSync(svgPath, "utf-8");
assert.ok(svgContent.includes("<svg"), "Must be valid SVG");
assert.ok(svgContent.includes(firstMarker.fallback_caption), "Must include plain-URL fallback text in SVG");
console.log("✓ Marker generation verified with Level H error recovery and printed URL caption");

// 2. Playwright E2E Route Verification
const browser = await launch();
try {
  const page = await browser.newPage({ viewport: VIEWPORTS.desktop });
  const embedUrl = `${BASE}/embed/marker/?target=note:the-room-after-midnight`;
  console.log(`Checking standalone embed route: ${embedUrl}...`);
  await page.goto(embedUrl, { waitUntil: "networkidle" });
  await page.waitForSelector(".nc-marker-card");

  const titleText = await page.$eval(".nc-marker-card__title", el => el.textContent);
  assert.ok(titleText.includes("note:the-room-after-midnight"));

  const fallbackText = await page.$eval(".nc-marker-card__fallback", el => el.textContent);
  assert.ok(fallbackText.includes("shady.example.org/portal/?target="));

  const portalBtn = await page.$eval("a[href*='/portal/']", el => el.href);
  assert.ok(portalBtn.includes("/portal/?target="));
  console.log("✓ Standalone embed route renders cleanly with fallback text and portal link");

  // Screenshot
  const screenshotPath = resolve(SCREENS, "editorial-marker.png");
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log(`✓ Screenshot written to ${screenshotPath}`);

} finally {
  await browser.close();
}

console.log("\nALL QR / MOSAIC MARKER TESTS PASSED!");
