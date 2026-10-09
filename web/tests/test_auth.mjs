import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { launch, VIEWPORTS } from "../tools/browser.mjs";

const require = createRequire(import.meta.url);
const AXE = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.env.BASE || "http://127.0.0.1:8088";
const DOCS = new URL("../../docs/", import.meta.url).pathname;

console.log("=== Testing Authentication & Passkey Dialog (Task 4.1) ===");

// 1. Verify build files
if (!existsSync("web/embed/auth-dialog/index.html")) {
  console.error("FAIL: Missing web/embed/auth-dialog/index.html");
  process.exit(1);
}
if (!existsSync("web/auth/index.html")) {
  console.error("FAIL: Missing web/auth/index.html");
  process.exit(1);
}
console.log("✓ Route files /auth/ and /embed/auth-dialog/ built cleanly");

const browser = await launch();

try {
  // 2. Audit /auth/ on mobile & desktop
  for (const [vpName, vp] of Object.entries(VIEWPORTS)) {
    for (const scheme of ["light", "dark"]) {
      const page = await browser.newPage({
        viewport: { width: vp.width, height: vp.height },
        ...vp,
        colorScheme: scheme,
        bypassCSP: true,
      });

      await page.goto(`${BASE}/auth/`, { waitUntil: "networkidle" });
      await page.waitForTimeout(200);

      // Verify DOM elements
      const hasTitle = await page.$eval(".nc-auth-card__title", el => el.textContent.length > 0);
      const hasTabs = await page.$$eval(".nc-auth-card__tab", els => els.length >= 2);
      if (!hasTitle || !hasTabs) {
        throw new Error(`DOM structure incomplete on /auth/ (${vpName} ${scheme})`);
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
        console.error(`Axe violations on /auth/ (${vpName} ${scheme}):`, axeResult.violations.map(v => v.id));
        throw new Error(`Axe violations found: ${axeResult.violations[0].id}`);
      }

      await page.close();
    }
  }
  console.log("✓ Full-page /auth/ verified across all viewports and color schemes with 0 Axe violations");

  // 3. Audit /embed/auth-dialog/
  {
    const page = await browser.newPage({
      viewport: { width: 390, height: 844 },
      colorScheme: "dark",
      bypassCSP: true,
    });

    await page.goto(`${BASE}/embed/auth-dialog/`, { waitUntil: "networkidle" });
    await page.waitForTimeout(200);

    await page.addScriptTag({ content: AXE });
    const axeResult = await page.evaluate(async () => {
      return await window.axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] },
        rules: { region: { enabled: false } },
      });
    });

    if (axeResult.violations.length > 0) {
      console.error("Axe violations on /embed/auth-dialog/:", axeResult.violations.map(v => v.id));
      throw new Error(`Axe violations found: ${axeResult.violations[0].id}`);
    }

    // Capture screenshot
    const screenPath = DOCS + "screens/auth-passkey-dialog.png";
    await page.screenshot({ path: screenPath });
    console.log(`✓ Screenshot captured at ${screenPath}`);

    // Test Tab Switching
    const tabs = await page.$$(".nc-auth-card__tab");
    if (tabs.length >= 2) {
      await tabs[1].click();
      await page.waitForTimeout(100);
      const isFallbackVisible = await page.$("#nc-auth-fallback-username");
      if (!isFallbackVisible) throw new Error("Fallback username input not rendered upon tab switch");
      console.log("✓ Tab switching to Username Fallback verified");
    }

    await page.close();
  }

  console.log("\nALL AUTHENTICATION & PASSKEY TESTS PASSED!");
} finally {
  await browser.close();
}
