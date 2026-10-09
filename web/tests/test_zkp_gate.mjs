import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { launch, VIEWPORTS } from "../tools/browser.mjs";

const require = createRequire(import.meta.url);
const AXE = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.env.BASE || "http://127.0.0.1:8088";
const DOCS = new URL("../../docs/", import.meta.url).pathname;

console.log("=== Testing 21+ ZKP Gate on Writes (Task 4.4) ===");

// 1. Verify build file
if (!existsSync("web/embed/zkp-gate/index.html")) {
  console.error("FAIL: Missing web/embed/zkp-gate/index.html");
  process.exit(1);
}
console.log("✓ Route file /embed/zkp-gate/ built cleanly");

const browser = await launch();

try {
  // 2. Audit /embed/zkp-gate/ on mobile & desktop across schemes
  for (const [vpName, vp] of Object.entries(VIEWPORTS)) {
    for (const scheme of ["light", "dark"]) {
      const page = await browser.newPage({
        viewport: { width: vp.width, height: vp.height },
        ...vp,
        colorScheme: scheme,
        bypassCSP: true,
      });

      await page.goto(`${BASE}/embed/zkp-gate/`, { waitUntil: "networkidle" });
      await page.waitForTimeout(200);

      // Verify DOM elements
      const title = await page.$eval("#nc-zkp-title", el => el.textContent.trim());
      if (!title.includes("21+ Community Write Gate")) {
        throw new Error(`Title not rendered correctly on /embed/zkp-gate/ (${vpName} ${scheme})`);
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
        console.error(`Axe violations on /embed/zkp-gate/ (${vpName} ${scheme}):`, axeResult.violations.map(v => v.id));
        throw new Error(`Axe violations found: ${axeResult.violations[0].id}`);
      }

      await page.close();
    }
  }
  console.log("✓ /embed/zkp-gate/ verified across all viewports and color schemes with 0 Axe violations");

  // 3. Test interactive verification and token reset
  {
    const page = await browser.newPage({
      viewport: { width: 390, height: 844 },
      colorScheme: "dark",
      bypassCSP: true,
    });

    // Mock API routes
    await page.route("**/api/auth/zkp/challenge", async route => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          challenge: "mock_challenge_abc123",
          predicate: "age >= 21",
        }),
      });
    });

    await page.route("**/api/auth/zkp/verify", async route => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          verified: true,
          token: "mock_zkp_token.sig12345",
          expires_at: Math.floor(Date.now() / 1000) + 86400,
        }),
      });
    });

    await page.goto(`${BASE}/embed/zkp-gate/`, { waitUntil: "networkidle" });
    await page.waitForTimeout(200);

    // Initial state: explainer is visible
    const explainer = await page.$(".nc-zkp-gate__explainer");
    if (!explainer) throw new Error("Gate explainer not rendered initially");

    // Capture initial screenshot
    const screenPath = DOCS + "screens/zkp-gate-dialog.png";
    await page.screenshot({ path: screenPath });
    console.log(`✓ Screenshot captured at ${screenPath}`);

    // Click verify button
    const verifyBtn = await page.$('button[type="submit"]');
    if (!verifyBtn) throw new Error("Verify submit button not found");
    await verifyBtn.click();
    await page.waitForTimeout(400);

    // Verify verified state card rendered
    const verifiedCard = await page.$(".nc-zkp-gate__card--verified");
    if (!verifiedCard) throw new Error("Verified card not rendered after successful verification");

    const badgeText = await page.$eval(".nc-zkp-gate__badge", el => el.textContent);
    if (!badgeText.includes("21+ Verified")) {
      throw new Error(`Badge text incorrect: "${badgeText}"`);
    }
    console.log(`✓ Verification succeeded: badge "${badgeText}" displayed`);

    // Reset token
    const clearBtn = await page.$(".nc-zkp-gate__actions button");
    await clearBtn.click();
    await page.waitForTimeout(300);

    // Explainer should be back
    const explainerAfter = await page.$(".nc-zkp-gate__explainer");
    if (!explainerAfter) throw new Error("Explainer did not return after clearing verification token");
    console.log("✓ Reset verification token flow verified");

    await page.close();
  }

} finally {
  await browser.close();
}

console.log("✓ Task 4.4 (21+ ZKP gate on writes) passed all browser and accessibility checks");
