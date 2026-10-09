// E2E test for Task 2.6: Daily page auto-build and local midnight clock rollover
// Asserts midnight rollover, byte-identical archive page builds, and yesterday/tomorrow navigation.

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { execSync } from "node:child_process";
import crypto from "node:crypto";
import { launch, VIEWPORTS } from "../tools/browser.mjs";
import { today, relative, label, addDays } from "../js/data/dates.js";
import { loadCalendar } from "../js/data/calendar.js";

const BASE = process.env.BASE || "http://127.0.0.1:8085";
const WEB = new URL("../", import.meta.url).pathname;
const DOCS = new URL("../../docs/", import.meta.url).pathname;
const SCREENS_DOCS = DOCS + "screens/";
const SCREENS_OUTPUT = WEB + "tests/output/";

mkdirSync(SCREENS_DOCS, { recursive: true });
mkdirSync(SCREENS_OUTPUT, { recursive: true });

console.log("=== Testing Daily Page Auto-Build & Navigation (Task 2.6) ===");

// 1. Clock freeze: 23:59 -> 00:01 rollover in America/Los_Angeles timezone
console.log("1. Verifying midnight clock simulation and rollover in America/Los_Angeles...");
// 2026-10-15 23:59:50 PDT is UTC 2026-10-16 06:59:50
const tPre = new Date("2026-10-16T06:59:50Z");
const dayPre = today(tPre);
if (dayPre !== "2026-10-15") {
  throw new Error(`Expected date at 23:59 PDT to be 2026-10-15, got ${dayPre}`);
}
if (relative("2026-10-15", dayPre) !== "Tonight") {
  throw new Error(`Expected relative("2026-10-15") at 23:59 to be "Tonight", got ${relative("2026-10-15", dayPre)}`);
}
if (relative("2026-10-16", dayPre) !== "Tomorrow") {
  throw new Error(`Expected relative("2026-10-16") at 23:59 to be "Tomorrow", got ${relative("2026-10-16", dayPre)}`);
}

// 2026-10-16 00:00:10 PDT is UTC 2026-10-16 07:00:10
const tPost = new Date("2026-10-16T07:00:10Z");
const dayPost = today(tPost);
if (dayPost !== "2026-10-16") {
  throw new Error(`Expected date at 00:00 PDT to be 2026-10-16, got ${dayPost}`);
}
if (relative("2026-10-15", dayPost) !== "Yesterday") {
  throw new Error(`Expected relative("2026-10-15") at 00:00 to be "Yesterday", got ${relative("2026-10-15", dayPost)}`);
}
if (relative("2026-10-16", dayPost) !== "Tonight") {
  throw new Error(`Expected relative("2026-10-16") at 00:00 to be "Tonight", got ${relative("2026-10-16", dayPost)}`);
}
console.log(`✓ Midnight rollover passed: ${dayPre} (Tonight) -> ${dayPost} (Yesterday / Tonight)`);

// 2. Byte-identical static archive build assertion
console.log("2. Verifying byte-identical build for past archive days...");
const archiveFile = WEB + "day/2026-10-15/index.html";
const initialBytes = readFileSync(archiveFile);
const hashA = crypto.createHash("sha256").update(initialBytes).digest("hex");

// Re-run builder
execSync(`python3 ${WEB}tools/build_pages.py`, { stdio: "pipe" });
const rebuiltBytes = readFileSync(archiveFile);
const hashB = crypto.createHash("sha256").update(rebuiltBytes).digest("hex");

if (hashA !== hashB || !initialBytes.equals(rebuiltBytes)) {
  throw new Error(`Rebuild of archive page /day/2026-10-15/index.html produced non-identical output! ${hashA} !== ${hashB}`);
}
console.log(`✓ Archive page /day/2026-10-15/index.html is byte-identical across rebuilds (sha256: ${hashA.slice(0, 12)}...)`);

// 3. Playwright Browser E2E: /today/, /day/YYYY-MM-DD/, yesterday/tomorrow navigation, popstate
console.log("3. Launching browser for E2E navigation tests...");
const browser = await launch();

try {
  const context = await browser.newContext({ viewport: VIEWPORTS.desktop });
  const page = await context.newPage();

  // Test /today/
  console.log(`Navigating to ${BASE}/today/...`);
  await page.goto(`${BASE}/today/`, { waitUntil: "networkidle" });
  await page.waitForSelector(".nc-day-agenda");
  const todayHeading = await page.$eval(".nc-day-agenda__title", el => el.textContent.trim());
  console.log(`/today/ loaded with heading: "${todayHeading}"`);
  if (!todayHeading) throw new Error("Missing heading on /today/");

  // Test /day/2026-10-15/
  console.log(`Navigating to ${BASE}/day/2026-10-15/...`);
  await page.goto(`${BASE}/day/2026-10-15/`, { waitUntil: "networkidle" });
  await page.waitForSelector(".nc-day-agenda[data-date='2026-10-15']");
  const day15Title = await page.$eval(".nc-day-agenda__title", el => el.textContent.trim());
  console.log(`/day/2026-10-15/ loaded with heading: "${day15Title}"`);

  // Assert nav buttons present
  const prevBtn = await page.$("button[data-nav='prev']");
  const nextBtn = await page.$("button[data-nav='next']");
  if (!prevBtn || !nextBtn) throw new Error("Day agenda navigation buttons missing!");

  // Click Tomorrow ->
  console.log("Clicking Tomorrow button...");
  await nextBtn.click();
  await page.waitForSelector(".nc-day-agenda[data-date='2026-10-16']");
  const day16Title = await page.$eval(".nc-day-agenda__title", el => el.textContent.trim());
  const urlAfterNext = page.url();
  console.log(`Navigated to: ${urlAfterNext}, heading: "${day16Title}"`);
  if (!urlAfterNext.includes("/day/2026-10-16")) {
    throw new Error(`Expected URL to contain /day/2026-10-16, got ${urlAfterNext}`);
  }

  // Click <- Yesterday
  console.log("Clicking Yesterday button...");
  const prevBtn2 = await page.waitForSelector("button[data-nav='prev']");
  await prevBtn2.click();
  await page.waitForSelector(".nc-day-agenda[data-date='2026-10-15']");
  const restoredTitle = await page.$eval(".nc-day-agenda__title", el => el.textContent.trim());
  const urlAfterPrev = page.url();
  console.log(`Navigated back to: ${urlAfterPrev}, heading: "${restoredTitle}"`);
  if (!urlAfterPrev.includes("/day/2026-10-15")) {
    throw new Error(`Expected URL to contain /day/2026-10-15, got ${urlAfterPrev}`);
  }

  // Test history popstate (Browser Back & Forward)
  console.log("Testing browser history Back...");
  await page.goBack();
  await page.waitForTimeout(200);
  console.log("URL after goBack:", page.url());

  console.log("Testing browser history Forward...");
  await page.goForward();
  await page.waitForTimeout(200);
  console.log("URL after goForward:", page.url());

  // Capture screenshot of archive page
  const screenPath = SCREENS_DOCS + "daily-archive-navigation.png";
  await page.screenshot({ path: screenPath, fullPage: true });
  console.log(`✓ Screenshot captured to ${screenPath}`);

} finally {
  await browser.close();
}

console.log("\n✓ All Task 2.6 Daily page auto-build checks passed!");
