import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { launch, VIEWPORTS } from "../tools/browser.mjs";

const require = createRequire(import.meta.url);
const AXE = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.env.BASE || "http://127.0.0.1:8094";
const API = process.env.API || BASE;
const DOCS = new URL("../../docs/", import.meta.url).pathname;

console.log("=== Testing Preference & Settings Tabs (Task 4.6) ===");

if (!existsSync("web/embed/preference-tabs/index.html")) {
  console.error("FAIL: Missing web/embed/preference-tabs/index.html");
  process.exit(1);
}
console.log("✓ Route file /embed/preference-tabs/ built");

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

const browser = await launch();

try {
  for (const [vpName, vp] of Object.entries(VIEWPORTS)) {
    for (const scheme of ["light", "dark"]) {
      const page = await browser.newPage({
        viewport: { width: vp.width, height: vp.height },
        ...vp,
        colorScheme: scheme,
        bypassCSP: true,
      });
      await page.goto(`${BASE}/embed/preference-tabs/`, { waitUntil: "networkidle" });
      await page.waitForSelector("#nc-prefs-title");
      const title = await page.$eval("#nc-prefs-title", el => el.textContent.trim());
      if (title !== "Settings") throw new Error(`Title mismatch on ${vpName} ${scheme}: ${title}`);
      const heights = await page.$$eval(".nc-prefs-tab, .nc-prefs-actions button", els =>
        els.map(el => Math.round(el.getBoundingClientRect().height))
      );
      for (const h of heights) {
        if (h < 44) throw new Error(`Control height ${h}px is under 44px on ${vpName}`);
      }
      await axe(page, `/embed/preference-tabs/ (${vpName} ${scheme})`);
      await page.close();
    }
  }
  console.log("✓ settings embed verified across viewports with 0 Axe violations");

  const username = `prefs_${Date.now()}`;
  const registered = await fetch(`${API}/api/auth/register/fallback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password: "prefs_pass_123", displayName: "Prefs" }),
  });
  if (!registered.ok) throw new Error(`register failed ${registered.status} ${await registered.text()}`);
  const reg = await registered.json();
  const token = reg.session_token;
  if (!token) throw new Error("register response missing session_token");

  const page = await browser.newPage({
    viewport: { width: 1280, height: 900 },
    colorScheme: "light",
    bypassCSP: true,
  });
  const url = `${BASE}/embed/preference-tabs/?session=${encodeURIComponent(token)}`;
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForSelector("#nc-prefs-title");

  await page.click('[data-tab="display"]');
  await page.click('input[name="nc-prefs-theme"][value="dark"]');
  await page.waitForFunction(() => document.documentElement.getAttribute("data-theme") === "dark");
  await page.click('input[name="nc-prefs-density"][value="compact"]');
  await page.waitForFunction(() => document.documentElement.getAttribute("data-density") === "compact");
  await page.click('input[name="nc-prefs-text_scale"][value="1.25"]');
  await page.click('[data-tab="notifications"]');
  await page.click("#nc-prefs-note-daily_digest");
  await page.click('[data-tab="muted"]');
  await page.fill("#nc-prefs-venue-input", "ven_cellar");
  await page.click("button:has-text('Add venue')");
  await page.waitForSelector("text=ven_cellar");
  await page.click('[data-tab="steward"]');
  await page.fill("#nc-prefs-steward-handle", "steward_test");
  await page.dispatchEvent("#nc-prefs-steward-handle", "change");
  await page.waitForFunction(() => document.getElementById("nc-prefs-live-status")?.textContent?.includes("saved"));

  await page.reload({ waitUntil: "networkidle" });
  await page.waitForFunction(() => document.documentElement.getAttribute("data-theme") === "dark");
  const theme = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
  const density = await page.evaluate(() => document.documentElement.getAttribute("data-density"));
  if (theme !== "dark") throw new Error(`theme did not persist: ${theme}`);
  if (density !== "compact") throw new Error(`density did not persist: ${density}`);
  await page.click('[data-tab="display"]');
  const scale = await page.$eval('input[name="nc-prefs-text_scale"][value="1.25"]', el => el.checked);
  if (!scale) throw new Error("text scale did not persist");
  await page.click('[data-tab="notifications"]');
  const digest = await page.$eval("#nc-prefs-note-daily_digest", el => el.checked);
  if (!digest) throw new Error("daily digest did not persist");
  await page.click('[data-tab="muted"]');
  const muted = await page.$eval(".nc-prefs-venue-list", el => el.textContent);
  if (!muted.includes("ven_cellar")) throw new Error("muted venue did not persist");
  await page.click('[data-tab="steward"]');
  const handle = await page.$eval("#nc-prefs-steward-handle", el => el.value);
  if (handle !== "steward_test") throw new Error(`handle did not persist: ${handle}`);

  const other = await fetch(`${API}/api/auth/preferences`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const body = await other.json();
  if (body.preferences?.theme !== "dark") throw new Error("API did not return the saved theme");
  if (!body.preferences.muted_venues?.includes("ven_cellar")) throw new Error("API did not return muted venues");

  await page.screenshot({ path: `${DOCS}screens/preference-tabs.png` });
  console.log("✓ settings persist across reload and the preferences API");
  await page.close();
} finally {
  await browser.close();
}

console.log("\nALL PREFERENCE TAB TESTS PASSED");
