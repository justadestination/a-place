import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { launch, VIEWPORTS } from "../tools/browser.mjs";

const require = createRequire(import.meta.url);
const AXE = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.env.BASE || "http://127.0.0.1:8096";
const DOCS = new URL("../../docs/", import.meta.url).pathname;

const TYPES = [
  ["promoter", "ent_promoter_lumen", "Lumen Presents"],
  ["band", "ent_band_wave", "Subterranean Wave Syndicate"],
  ["comedian", "ent_comic_null", "Mara Voss"],
  ["other", "ent_other_paper", "Night Paper"],
];

console.log("=== Testing Entity Pages (Task 2.13) ===");

if (!existsSync("web/entity/index.html")) {
  console.error("FAIL: Missing web/entity/index.html");
  process.exit(1);
}
console.log("✓ Route file /entity/ built");

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
    for (const [type, id, name] of TYPES) {
      const page = await browser.newPage({
        viewport: { width: vp.width, height: vp.height },
        ...vp,
        colorScheme: "dark",
        bypassCSP: true,
      });
      await page.goto(`${BASE}/embed/entity-page/?type=${type}&id=${id}`, { waitUntil: "networkidle" });
      await page.waitForSelector("#nc-entity-title");
      const title = await page.$eval("#nc-entity-title", el => el.textContent.trim());
      if (title !== name) throw new Error(`${type} title mismatch: ${title}`);
      const headings = await page.$$eval("h2", els => els.map(el => el.textContent.trim()));
      for (const needed of ["Profile", "Contact", "Linked events", "Linked zine articles"]) {
        if (!headings.includes(needed)) throw new Error(`${type} missing ${needed}`);
      }
      const heights = await page.$$eval(".nc-entity-link, .nc-entity-page__contact-link", els =>
        els.map(el => Math.round(el.getBoundingClientRect().height))
      );
      for (const height of heights) {
        if (height < 44) throw new Error(`Link height ${height}px is under 44px on ${type}`);
      }
      await axe(page, `/embed/entity-page/ ${type} (${vpName})`);
      if (type === "band" && vpName === "desktop") {
        const hrefs = await page.$$eval("a", els => els.map(el => el.getAttribute("href") || ""));
        if (!hrefs.some(href => href.includes("ent_band_wave"))) throw new Error("band page missing entity link");
        if (!hrefs.some(href => href.includes("zine_wave_note"))) throw new Error("band page missing article link");
        await page.screenshot({ path: `${DOCS}screens/entity-page.png` });
      }
      await page.close();
    }
  }
  console.log("✓ all entity types verified across viewports with 0 Axe violations");
} finally {
  await browser.close();
}

console.log("\nALL ENTITY PAGE TESTS PASSED");
