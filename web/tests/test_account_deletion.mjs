import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { launch, VIEWPORTS } from "../tools/browser.mjs";

const require = createRequire(import.meta.url);
const AXE = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.env.BASE || "http://127.0.0.1:8088";
const DOCS = new URL("../../docs/", import.meta.url).pathname;

console.log("=== Testing Account Deletion & Data Export (Task 4.5) ===");

// 1. Verify build file
if (!existsSync("web/embed/account-settings/index.html")) {
  console.error("FAIL: Missing web/embed/account-settings/index.html");
  process.exit(1);
}
console.log("✓ Route file /embed/account-settings/ built cleanly");

const browser = await launch();

try {
  // 2. Audit /embed/account-settings/ across viewports and color schemes with Axe
  for (const [vpName, vp] of Object.entries(VIEWPORTS)) {
    for (const scheme of ["light", "dark"]) {
      const page = await browser.newPage({
        viewport: { width: vp.width, height: vp.height },
        ...vp,
        colorScheme: scheme,
        bypassCSP: true,
      });

      await page.goto(`${BASE}/embed/account-settings/`, { waitUntil: "networkidle" });
      await page.waitForTimeout(150);

      // Verify DOM elements
      const title = await page.$eval("#nc-account-title", el => el.textContent.trim());
      if (!title.includes("Account Data & Lifecycle")) {
        throw new Error(`Title not rendered correctly on /embed/account-settings/ (${vpName} ${scheme})`);
      }

      // Check touch target height on primary actions
      const btnHeights = await page.$$eval(".nc-account-actions button", els =>
        els.map(el => Math.round(el.getBoundingClientRect().height))
      );
      for (const h of btnHeights) {
        if (h < 44) {
          throw new Error(`Button height ${h}px is less than WCAG 2.2 target size 44px on ${vpName}`);
        }
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
        console.error(`Axe violations on /embed/account-settings/ (${vpName} ${scheme}):`, axeResult.violations.map(v => v.id));
        throw new Error(`Axe violations found: ${axeResult.violations[0].id}`);
      }

      await page.close();
    }
  }
  console.log("✓ /embed/account-settings/ verified across all viewports and color schemes with 0 Axe violations");

  // 3. Test interactive export and confirmation flow
  const testPage = await browser.newPage({
    viewport: { width: 1280, height: 800 },
    colorScheme: "dark",
    bypassCSP: true,
  });

  await testPage.goto(`${BASE}/embed/account-settings/`, { waitUntil: "networkidle" });
  await testPage.waitForTimeout(200);

  // Click export
  await testPage.click("#nc-export-btn");
  await testPage.waitForTimeout(200);
  const feedback = await testPage.$eval("#nc-export-feedback", el => el.textContent.trim());
  if (!feedback.includes("Export complete")) {
    throw new Error(`Expected export feedback, got: "${feedback}"`);
  }
  console.log("✓ Personal data export trigger verified");

  // Open delete modal
  await testPage.click("#nc-open-delete-modal-btn");
  await testPage.waitForTimeout(150);

  const isModalVisible = await testPage.$eval("#nc-delete-dialog", el => !el.hasAttribute("hidden"));
  if (!isModalVisible) {
    throw new Error("Modal dialog did not open when clicking Delete My Account");
  }

  // Verify confirm delete button is disabled initially
  let isBtnDisabled = await testPage.$eval("#nc-confirm-delete-btn", el => el.hasAttribute("disabled"));
  if (!isBtnDisabled) {
    throw new Error("Confirm delete button must be disabled before confirmation");
  }

  // Type wrong username
  await testPage.type("#nc-confirm-username-input", "random_user");
  await testPage.click("#nc-confirm-checkbox");
  await testPage.waitForTimeout(100);
  isBtnDisabled = await testPage.$eval("#nc-confirm-delete-btn", el => el.hasAttribute("disabled"));
  if (!isBtnDisabled) {
    throw new Error("Confirm delete button must stay disabled when username does not match");
  }

  // Clear and type exact username "solaris"
  await testPage.fill("#nc-confirm-username-input", "solaris");
  await testPage.waitForTimeout(100);
  isBtnDisabled = await testPage.$eval("#nc-confirm-delete-btn", el => el.hasAttribute("disabled"));
  if (isBtnDisabled) {
    throw new Error("Confirm delete button should become enabled when username matches and checkbox is checked");
  }

  // Execute deletion
  await testPage.click("#nc-confirm-delete-btn");
  await testPage.waitForTimeout(300);

  // Assert deleted state alert banner is displayed
  const deletedBanner = await testPage.$eval("#nc-account-deleted-alert", el => el.textContent.trim());
  if (!deletedBanner.includes("Account Successfully Deleted")) {
    throw new Error(`Expected deleted banner, got: "${deletedBanner}"`);
  }
  console.log("✓ Account deletion confirmation and transition to deleted state verified");

  // Re-audit deleted state for accessibility
  await testPage.addScriptTag({ content: AXE });
  const finalAxe = await testPage.evaluate(async () => {
    return await window.axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] },
      rules: { region: { enabled: false } },
    });
  });
  if (finalAxe.violations.length > 0) {
    throw new Error(`Axe violation in deleted state: ${finalAxe.violations[0].id}`);
  }
  console.log("✓ Deleted state verified with 0 Axe violations");

  // Capture screenshot
  await testPage.screenshot({ path: `${DOCS}screens/account-deletion-export.png` });
  console.log(`✓ Screenshot captured at docs/screens/account-deletion-export.png`);

  await testPage.close();
  console.log("=== All Task 4.5 E2E Tests PASSED ===");
} finally {
  await browser.close();
}
