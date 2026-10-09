import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { launch, VIEWPORTS } from "../tools/browser.mjs";

const require = createRequire(import.meta.url);
const AXE = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.env.BASE || "http://127.0.0.1:8088";
const DOCS = new URL("../../docs/", import.meta.url).pathname;

console.log("=== Testing Lost-Phone Recovery (Task 4.2) ===");

// 1. Verify build file
if (!existsSync("web/embed/recovery/index.html")) {
  console.error("FAIL: Missing web/embed/recovery/index.html");
  process.exit(1);
}
console.log("✓ Route file /embed/recovery/ built cleanly");

const browser = await launch();

try {
  // 2. Audit /embed/recovery/ on mobile & desktop across schemes
  for (const [vpName, vp] of Object.entries(VIEWPORTS)) {
    for (const scheme of ["light", "dark"]) {
      const page = await browser.newPage({
        viewport: { width: vp.width, height: vp.height },
        ...vp,
        colorScheme: scheme,
        bypassCSP: true,
      });

      await page.goto(`${BASE}/embed/recovery/`, { waitUntil: "networkidle" });
      await page.waitForTimeout(200);

      // Verify DOM elements
      const title = await page.$eval("#nc-recovery-title", el => el.textContent.trim());
      if (!title.includes("Lost Authenticator Recovery")) {
        throw new Error(`Title not rendered correctly on /embed/recovery/ (${vpName} ${scheme})`);
      }

      const tabs = await page.$$(".nc-recovery__tab");
      if (tabs.length !== 2) {
        throw new Error(`Expected 2 recovery tabs, found ${tabs.length}`);
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
        console.error(`Axe violations on /embed/recovery/ (${vpName} ${scheme}):`, axeResult.violations.map(v => v.id));
        throw new Error(`Axe violations found: ${axeResult.violations[0].id}`);
      }

      await page.close();
    }
  }
  console.log("✓ /embed/recovery/ verified across all viewports and color schemes with 0 Axe violations");

  // 3. Test interactive validation, failure banners, and escalation flow
  {
    const page = await browser.newPage({
      viewport: { width: 390, height: 844 },
      colorScheme: "dark",
      bypassCSP: true,
    });

    await page.route("**/api/auth/recovery/verify", async route => {
      const postData = JSON.parse(route.request().postData() || "{}");
      if (postData.recoveryCode === "NC-INVALID-CODE") {
        await route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ error: "Invalid username or recovery code" }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            success: true,
            user: { id: "u_recovery", username: postData.username || "nightowl" },
            session_token: "st_recovery_12345",
          }),
        });
      }
    });

    await page.route("**/api/auth/recovery/escalate", async route => {
      const postData = JSON.parse(route.request().postData() || "{}");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          escalation: {
            id: "esc_999888",
            username: postData.username,
            contact_info: postData.contact,
            status: "pending",
          },
        }),
      });
    });

    await page.goto(`${BASE}/embed/recovery/`, { waitUntil: "networkidle" });
    await page.waitForTimeout(200);

    // Initial state: self-service tab is active
    const usernameInput = await page.$("#nc-rec-username");
    const codeInput = await page.$("#nc-rec-code");
    if (!usernameInput || !codeInput) {
      throw new Error("Self-service form inputs not found");
    }

    // Capture initial screenshot
    const screenPath = DOCS + "screens/lost-phone-recovery.png";
    await page.screenshot({ path: screenPath });
    console.log(`✓ Screenshot captured at ${screenPath}`);

    // Try submitting with invalid code
    await usernameInput.fill("nightowl");
    await codeInput.fill("NC-INVALID-CODE");
    await page.click('button[type="submit"]');
    await page.waitForTimeout(400);

    const alertMsg = await page.$eval('[role="alert"]', el => el.textContent);
    if (!alertMsg || alertMsg.length === 0) {
      throw new Error("Expected alert error banner on invalid code submission");
    }
    console.log(`✓ Invalid recovery code properly rejected with alert: "${alertMsg}"`);

    // Switch to support escalation tab
    const escTab = await page.$("#nc-tab-escalate");
    await escTab.click();
    await page.waitForTimeout(200);

    const escUsername = await page.$("#nc-esc-username");
    const escContact = await page.$("#nc-esc-contact");
    const escNotes = await page.$("#nc-esc-notes");
    if (!escUsername || !escContact || !escNotes) {
      throw new Error("Escalation form fields not rendered");
    }

    // Submit escalation
    await escUsername.fill("lostphoneuser");
    await escContact.fill("lostuser@signal.me");
    await escNotes.fill("Left iPhone on Muni train; no paper recovery codes retained.");
    await page.click('button[type="submit"]');
    await page.waitForTimeout(500);

    const statusBanner = await page.$eval(".nc-recovery__banner--success", el => el.textContent);
    if (!statusBanner.includes("Escalation ticket submitted")) {
      throw new Error(`Expected escalation confirmation banner, got: "${statusBanner}"`);
    }
    console.log(`✓ Escalation flow verified with confirmation: "${statusBanner}"`);

    await page.close();
  }

} finally {
  await browser.close();
}

console.log("✓ Task 4.2 (Lost-phone recovery) passed all browser and accessibility checks");
