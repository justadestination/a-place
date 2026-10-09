// E2E test for Task 3.3: Corrections UI
// Verifies contract spec's correction semantics:
//   1. Append + outrank: submitted correction appends to ledger and outranks original text.
//   2. Separate Forget control: policy redaction tombstone honors retention rules.
//   3. Visual verification screenshot.

import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { launch, VIEWPORTS } from "../tools/browser.mjs";
import { submitCorrection, requestForget, getCorrections } from "../components/corrections/corrections.js";

const BASE = process.env.BASE || "http://127.0.0.1:8085";
const WEB = new URL("../", import.meta.url).pathname;
const DOCS = new URL("../../docs/", import.meta.url).pathname;
const SCREENS_DOCS = DOCS + "screens/";
const SCREENS_OUTPUT = WEB + "tests/output/";

mkdirSync(SCREENS_DOCS, { recursive: true });
mkdirSync(SCREENS_OUTPUT, { recursive: true });

console.log("=== Testing Corrections UI (Task 3.3) ===");

// ---------------------------------------------------------------------------
// 1. Unit & Semantics Test: Append + Outrank and Forget Controls
// ---------------------------------------------------------------------------
console.log("\n1. Testing append + outrank and forget semantics...");
const testNodeId = "note:the-room-after-midnight";

// Initial state
const initialCorrections = getCorrections(testNodeId);
console.log(`Initial corrections count: ${initialCorrections.length}`);

// Submit correction
const correctionEntry = submitCorrection(testNodeId, {
  text: "Door opens at 11:30 PM, not midnight. Verified with venue promoter.",
  rationale: "Promoter call confirmation",
  submitter: "Steward-0x44",
});

if (!correctionEntry.outranks) {
  throw new Error("Submitted correction must specify outranks = true");
}
if (correctionEntry.kind !== "correction") {
  throw new Error("Entry kind must be 'correction'");
}

const afterSubmit = getCorrections(testNodeId);
if (afterSubmit.length !== initialCorrections.length + 1) {
  throw new Error("Correction was not appended to ledger");
}
console.log("✓ Append + outrank verified: entry appended with outranks=true.");

// Submit Forget control
const forgetEntry = requestForget(testNodeId, {
  reason: "Request under section 4.2 retention policy",
  submitter: "Article Author",
});

if (forgetEntry.kind !== "forget" || !forgetEntry.outranks) {
  throw new Error("Forget entry must be kind 'forget' and outrank original");
}

const afterForget = getCorrections(testNodeId);
if (afterForget.length !== afterSubmit.length + 1) {
  throw new Error("Forget record was not appended");
}
console.log("✓ Separate Forget control verified: tombstone record appended under retention policy.");

// ---------------------------------------------------------------------------
// 2. Browser E2E Test: Submit correction via UI and verify DOM outranking
// ---------------------------------------------------------------------------
console.log("\n2. Testing browser UI interaction on /embed/corrections/ and /zine/...");
const browser = await launch();
const page = await browser.newPage({ viewport: VIEWPORTS.desktop });

try {
  // Test standalone embed route
  await page.goto(`${BASE}/embed/corrections/?node=note%3Athe-room-after-midnight`, { waitUntil: "networkidle" });
  await page.waitForSelector(".nc-corrections");

  // Open submission form via button
  const submitBtn = page.locator("button:has-text('Submit Correction')");
  await submitBtn.click();
  await page.waitForSelector(".nc-corrections__form");

  // Fill and submit correction in browser
  await page.fill(".nc-corrections__textarea", "Live correction submitted via form: Stage relocated to back patio.");
  await page.fill(".nc-corrections__input", "Acoustic observation");
  await page.click("button:has-text('Commit Correction')");

  await page.waitForTimeout(200);

  // Verify outranking entries are present after submit
  const outrankingCount = await page.locator(".nc-correction-entry--outranking").count();
  console.log(`Outranking correction entries rendered: ${outrankingCount}`);
  if (outrankingCount < 1) {
    throw new Error("Outranking correction entry not rendered in DOM");
  }

  const badgeText = await page.locator(".nc-correction-entry__badge").first().textContent();
  console.log(`Badge text: "${badgeText}"`);
  if (!badgeText.includes("Outranks Original")) {
    throw new Error("Outranking badge missing from correction display");
  }

  // Assert new entry appears in the DOM
  const hasNewCorrection = await page.evaluate(() => {
    return document.body.textContent.includes("Stage relocated to back patio.");
  });
  if (!hasNewCorrection) {
    throw new Error("Submitted correction did not render immediately in DOM");
  }
  console.log("✓ UI submission verified: correction rendered and appended.");

  // Test inside /zine/ reader
  await page.goto(`${BASE}/zine/?node=note%3Athe-room-after-midnight`, { waitUntil: "networkidle" });
  await page.waitForSelector(".nc-reader");

  // Capture screenshot of corrections section in reader
  const screenshotPath = join(SCREENS_DOCS, "corrections-ui.png");
  await page.locator(".nc-corrections").screenshot({ path: screenshotPath });
  console.log(`✓ Screenshot captured to ${screenshotPath}`);

} finally {
  await browser.close();
}

console.log("\n=== All Corrections UI (Task 3.3) tests passed successfully! ===");
