import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { launch, VIEWPORTS } from "../tools/browser.mjs";

const require = createRequire(import.meta.url);
const AXE = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.env.BASE || "http://127.0.0.1:8088";
const DOCS = new URL("../../docs/", import.meta.url).pathname;

console.log("=== Testing Session Management & Devices (Task 4.3) ===");

// 1. Verify build file
if (!existsSync("web/embed/session-list/index.html")) {
  console.error("FAIL: Missing web/embed/session-list/index.html");
  process.exit(1);
}
console.log("✓ Route file /embed/session-list/ built cleanly");

const browser = await launch();

try {
  // 2. Audit /embed/session-list/ on mobile & desktop
  for (const [vpName, vp] of Object.entries(VIEWPORTS)) {
    for (const scheme of ["light", "dark"]) {
      const page = await browser.newPage({
        viewport: { width: vp.width, height: vp.height },
        ...vp,
        colorScheme: scheme,
        bypassCSP: true,
      });

      await page.goto(`${BASE}/embed/session-list/`, { waitUntil: "networkidle" });
      await page.waitForTimeout(200);

      // Verify DOM elements
      const title = await page.$eval("#nc-sessions-title", el => el.textContent.trim());
      if (!title.includes("Active Sessions")) {
        throw new Error(`Title not rendered correctly on /embed/session-list/ (${vpName} ${scheme})`);
      }

      const items = await page.$$(".nc-session-item");
      if (items.length < 2) {
        throw new Error(`Expected at least 2 sessions rendered, got ${items.length} (${vpName} ${scheme})`);
      }

      // Check badge on current device
      const hasCurrentBadge = await page.$eval(".nc-session-item--current .nc-session-item__badge", el => el.textContent.trim());
      if (hasCurrentBadge !== "This Device") {
        throw new Error(`Current device badge missing or incorrect: ${hasCurrentBadge}`);
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
        console.error(`Axe violations on /embed/session-list/ (${vpName} ${scheme}):`, axeResult.violations.map(v => v.id));
        throw new Error(`Axe violations found: ${axeResult.violations[0].id}`);
      }

      await page.close();
    }
  }
  console.log("✓ /embed/session-list/ verified across all viewports and color schemes with 0 Axe violations");

  // 3. Test interactive revocation flows
  {
    const page = await browser.newPage({
      viewport: { width: 390, height: 844 },
      colorScheme: "dark",
      bypassCSP: true,
    });

    await page.goto(`${BASE}/embed/session-list/`, { waitUntil: "networkidle" });
    await page.waitForTimeout(200);

    // Initial count
    const initialItems = await page.$$(".nc-session-item");
    if (initialItems.length !== 3) {
      throw new Error(`Expected initial 3 sessions, found ${initialItems.length}`);
    }

    // Capture screenshot before revocation
    const screenPath = DOCS + "screens/session-management-list.png";
    await page.screenshot({ path: screenPath });
    console.log(`✓ Screenshot captured at ${screenPath}`);

    // Click revoke on first remote session
    const revokeBtn = await page.$('.nc-session-item:not(.nc-session-item--current) button[aria-label*="Revoke"]');
    if (!revokeBtn) {
      throw new Error("Revoke button for remote session not found");
    }
    await revokeBtn.click();
    await page.waitForTimeout(200);

    // Assert count decremented to 2
    const itemsAfterOne = await page.$$(".nc-session-item");
    if (itemsAfterOne.length !== 2) {
      throw new Error(`Expected 2 sessions after single revoke, got ${itemsAfterOne.length}`);
    }

    // Check status announcement
    const statusText = await page.$eval('[role="status"]', el => el.textContent);
    if (!statusText.includes("Signed out")) {
      throw new Error(`Status announcement did not confirm sign out: "${statusText}"`);
    }

    // Click "Sign out all other devices"
    const revokeAllBtn = await page.$(".nc-session-list__revoke-all");
    if (!revokeAllBtn) {
      throw new Error("Sign out all other devices button not found");
    }
    await revokeAllBtn.click();
    await page.waitForTimeout(200);

    // Assert only 1 session remains (the current session)
    const itemsAfterAll = await page.$$(".nc-session-item");
    if (itemsAfterAll.length !== 1) {
      throw new Error(`Expected exactly 1 session remaining after revoke-all, got ${itemsAfterAll.length}`);
    }

    const remainingIsCurrent = await page.$eval(".nc-session-item", el => el.classList.contains("nc-session-item--current"));
    if (!remainingIsCurrent) {
      throw new Error("Remaining session is not marked as current device");
    }

    console.log("✓ Interactive single-revoke and revoke-all-others flows verified successfully");
    await page.close();
  }

} finally {
  await browser.close();
}

console.log("✓ Task 4.3 (Session management) passed all browser and accessibility checks");
