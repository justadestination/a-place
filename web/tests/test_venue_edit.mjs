import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { launch, VIEWPORTS } from "../tools/browser.mjs";

const require = createRequire(import.meta.url);
const AXE = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.env.BASE || "http://127.0.0.1:8097";
const API = process.env.API || "http://127.0.0.1:8098";
const DOCS = new URL("../../docs/", import.meta.url).pathname;

console.log("=== Testing Venue Quick-Edit (Task 2.14) ===");

if (!existsSync("web/edit/index.html")) {
  console.error("FAIL: Missing web/edit/index.html");
  process.exit(1);
}

async function axe(page, label) {
  await page.addScriptTag({ content: AXE });
  const axeResult = await page.evaluate(async () => {
    return await window.axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] },
      rules: { region: { enabled: false } },
    });
  });
  if (axeResult.violations.length > 0) {
    console.error(`Axe violations on ${label}:`, axeResult.violations.map(v => v.id));
    throw new Error(`Axe violations found: ${axeResult.violations[0].id}`);
  }
}

async function register(username) {
  const resp = await fetch(`${API}/api/auth/register/fallback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password: "edit_pass_123", displayName: username }),
  });
  if (!resp.ok) throw new Error(`register ${username} failed ${resp.status} ${await resp.text()}`);
  const body = await resp.json();
  if (!body.session_token) throw new Error("missing session_token");
  return body.session_token;
}

async function zkpToken() {
  const resp = await fetch(`${API}/api/auth/zkp/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ challenge: "test-challenge", claim: "age_over_21", status: "valid" }),
  });
  if (!resp.ok) throw new Error(`zkp verify failed ${resp.status} ${await resp.text()}`);
  const body = await resp.json();
  const token = body.token || body.zkp_token || body.proof?.token;
  if (!token) throw new Error(`zkp response missing token: ${JSON.stringify(body)}`);
  return token;
}

const browser = await launch();

try {
  const stamp = Date.now();
  const tokenA = await register(`owner_${stamp}`);
  const tokenB = await register(`other_${stamp}`);
  const zkp = await zkpToken();
  const venueId = `ven_quick_${stamp}`;
  const news = `Doors at eight ${stamp}`;

  for (const [vpName, vp] of Object.entries(VIEWPORTS)) {
    const page = await browser.newPage({
      viewport: { width: vp.width, height: vp.height },
      ...vp,
      colorScheme: "dark",
      bypassCSP: true,
    });
    const url = `${BASE}/embed/venue-edit/?id=${venueId}&session=${encodeURIComponent(tokenA)}&zkp=${encodeURIComponent(zkp)}`;
    await page.goto(url, { waitUntil: "networkidle" });
    await page.waitForSelector("#nc-edit-title");
    const heights = await page.$$eval(".nc-venue-edit__input, .nc-button", els =>
      els.map(el => Math.round(el.getBoundingClientRect().height))
    );
    for (const height of heights) {
      if (height < 44) throw new Error(`Control height ${height}px is under 44px on ${vpName}`);
    }
    await axe(page, `/embed/venue-edit/ (${vpName})`);
    await page.close();
  }

  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, colorScheme: "light", bypassCSP: true });
  const url = `${BASE}/embed/venue-edit/?id=${venueId}&session=${encodeURIComponent(tokenA)}&zkp=${encodeURIComponent(zkp)}`;
  const started = Date.now();
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.getElementById("nc-edit-status")?.textContent?.includes("You can edit"));
  await page.fill("#nc-edit-name", "The Cellar");
  await page.fill("#nc-edit-address", "1 Main Street");
  await page.click("button:has-text('Save details')");
  await page.waitForFunction(() => document.getElementById("nc-edit-status")?.textContent?.includes("saved"));
  await page.fill("#nc-edit-show-title", "Friday set");
  await page.fill("#nc-edit-date", "2026-10-16");
  await page.fill("#nc-edit-start", "20:00");
  await page.click("button:has-text('Add show')");
  await page.waitForFunction(() => document.getElementById("nc-edit-status")?.textContent?.includes("Show added"));
  await page.fill("#nc-edit-news-title", news);
  await page.fill("#nc-edit-news-text", "The Friday set starts at eight.");
  await page.click("button:has-text('Publish news')");
  await page.waitForSelector(`text=${news}`);
  const elapsed = Date.now() - started;
  if (elapsed >= 120000) throw new Error(`edit flow took ${elapsed}ms`);
  await page.screenshot({ path: `${DOCS}screens/venue-edit.png` });
  console.log(`✓ edit flow finished in ${elapsed}ms and the blurb is on the edit page`);

  const venue = await browser.newPage({ viewport: { width: 1280, height: 900 }, bypassCSP: true });
  await venue.goto(`${BASE}/embed/venue-page/?id=${venueId}`, { waitUntil: "networkidle" });
  await venue.waitForSelector(`text=${news}`);
  console.log("✓ blurb is on the venue page");
  await venue.close();
  await page.close();

  const denied = await fetch(`${API}/api/venues/edit`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${tokenB}`,
      "X-ZKP-Token": zkp,
    },
    body: JSON.stringify({ venue_id: venueId, op: "update", address: "somewhere else" }),
  });
  if (denied.status !== 403) throw new Error(`expected 403 for the other user, got ${denied.status} ${await denied.text()}`);
  console.log("✓ another user cannot edit the venue");
} finally {
  await browser.close();
}

console.log("\nALL VENUE EDIT TESTS PASSED");
