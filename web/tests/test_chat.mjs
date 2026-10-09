import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { launch, VIEWPORTS } from "../tools/browser.mjs";

const require = createRequire(import.meta.url);
const AXE = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.env.BASE || "http://127.0.0.1:8085";
const DOCS = new URL("../../docs/", import.meta.url).pathname;

console.log("=== Testing Embedded Matrix Chat Node (Task 5.1) ===");

if (!existsSync("web/chat/index.html")) {
  console.error("FAIL: Missing web/chat/index.html");
  process.exit(1);
}
if (!existsSync("web/embed/chat/index.html")) {
  console.error("FAIL: Missing web/embed/chat/index.html");
  process.exit(1);
}
if (!existsSync("docs/architecture/embedded_chat_matrix.md")) {
  console.error("FAIL: Missing docs/architecture/embedded_chat_matrix.md");
  process.exit(1);
}
console.log("✓ Route files /chat/ and /embed/chat/ built cleanly");

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

      const start = Date.now();
      await page.goto(`${BASE}/embed/chat/`, { waitUntil: "networkidle" });
      const loadTime = Date.now() - start;
      if (loadTime > 2500) {
        console.warn(`Warning: Chat node loaded in ${loadTime}ms (target <2000ms)`);
      }

      await page.waitForTimeout(150);

      // Verify auto-login pseudonym badge
      const pseudo = await page.$eval("#nc-chat-my-pseudonym", el => el.textContent.trim());
      if (!pseudo || !pseudo.startsWith("@anon-")) {
        throw new Error(`Expected anonymous pseudonym starting with @anon-, got: '${pseudo}'`);
      }

      // Verify touch target heights (>= 44px)
      const heights = await page.$$eval(".nc-chat__room-btn, #nc-chat-send-btn, #nc-chat-composer-input, .nc-chat__external-link", els =>
        els.map(el => Math.round(el.getBoundingClientRect().height))
      );
      for (const h of heights) {
        if (h < 43.5) {
          throw new Error(`Interactive element height ${h}px under 44px threshold on ${vpName}`);
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
        throw new Error(`Axe violations on /embed/chat/ (${vpName} ${scheme}): ${axeResult.violations.map(v => v.id).join(", ")}`);
      }

      await page.close();
    }
  }

  // Functional test on desktop
  const page = await browser.newPage({
    viewport: { width: 1280, height: 800 },
    colorScheme: "dark",
    bypassCSP: true,
  });

  await page.goto(`${BASE}/embed/chat/`, { waitUntil: "networkidle" });
  await page.waitForTimeout(200);

  // Type a message
  await page.fill("#nc-chat-composer-input", "Heading to downtown Santa Rosa tonight!");
  await page.click("#nc-chat-send-btn");
  await page.waitForTimeout(300);

  const messagesText = await page.$eval("#nc-chat-log", el => el.textContent);
  if (!messagesText.includes("Heading to downtown Santa Rosa tonight!")) {
    throw new Error("Sent message not found in message log");
  }

  // Ask Steward
  await page.fill("#nc-chat-composer-input", "@steward what's on tonight?");
  await page.click("#nc-chat-send-btn");
  await page.waitForTimeout(500);

  const updatedLog = await page.$eval("#nc-chat-log", el => el.textContent);
  if (!updatedLog.includes("@steward") || !updatedLog.includes("Downtown Santa Rosa")) {
    throw new Error("Steward response not found in chat log after asking what's on tonight");
  }

  // Capture screenshot
  await page.screenshot({ path: `${DOCS}screens/chat-node.png` });
  console.log("✓ Screenshot saved to docs/screens/chat-node.png");

  console.log("✓ All embedded chat node checks passed cleanly");
} finally {
  await browser.close();
}
