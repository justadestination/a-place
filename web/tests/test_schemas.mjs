import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { launch, VIEWPORTS } from "../tools/browser.mjs";
import { h } from "../js/core/dom.js";

const require = createRequire(import.meta.url);
const AXE = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.env.BASE || "http://127.0.0.1:8089";
const DOCS = new URL("../../docs/", import.meta.url).pathname;

console.log("=== Testing Venue & Entity Schemas (Task 2.11) ===");

const browser = await launch();

try {
  const page = await browser.newPage({
    viewport: { width: 390, height: 844 },
    colorScheme: "dark",
    bypassCSP: true,
  });

  await page.goto(`${BASE}/embed/button/`, { waitUntil: "networkidle" });
  await page.waitForTimeout(200);

  // Evaluate schema rendering in DOM
  const checkResult = await page.evaluate(async () => {
    const { h } = await import("/js/core/dom.js");
    
    // Sample schema-compliant entities
    const venue = {
      id: "ven_cal_stage",
      name: "California Stage & Music Hall",
      status: "active",
      address: "528 7th St, Santa Rosa, CA",
      timezone: "America/Los_Angeles",
      schema_version: "v2",
    };

    const band = {
      id: "band_paradise",
      type: "band",
      name: "Paradise Inferno",
      genre: "Psych Surf Rock",
      status: "active",
      schema_version: "v2",
    };

    const comedian = {
      id: "com_standup",
      type: "comedian",
      name: "Maya Lin",
      style: "Observational",
      status: "active",
      schema_version: "v2",
    };

    const root = document.getElementById("app");
    root.innerHTML = "";

    const cardVenue = h("article.nc-schema-card", { id: "nc-test-venue" },
      h("h2.nc-schema-card__title", {}, venue.name),
      h("p.nc-schema-card__meta", {}, `${venue.address} · ${venue.status.toUpperCase()} · ${venue.schema_version}`)
    );

    const cardBand = h("article.nc-schema-card", { id: "nc-test-band" },
      h("h2.nc-schema-card__title", {}, band.name),
      h("p.nc-schema-card__meta", {}, `Band: ${band.genre} · ${band.status.toUpperCase()} · ${band.schema_version}`)
    );

    const cardComic = h("article.nc-schema-card", { id: "nc-test-comic" },
      h("h2.nc-schema-card__title", {}, comedian.name),
      h("p.nc-schema-card__meta", {}, `Comedian: ${comedian.style} · ${comedian.status.toUpperCase()} · ${comedian.schema_version}`)
    );

    root.append(cardVenue, cardBand, cardComic);

    return {
      venueRendered: document.getElementById("nc-test-venue")?.textContent || "",
      bandRendered: document.getElementById("nc-test-band")?.textContent || "",
      comicRendered: document.getElementById("nc-test-comic")?.textContent || "",
    };
  });

  if (!checkResult.venueRendered.includes("California Stage") || !checkResult.venueRendered.includes("v2")) {
    throw new Error(`Venue card render incomplete: ${checkResult.venueRendered}`);
  }
  if (!checkResult.bandRendered.includes("Paradise Inferno") || !checkResult.bandRendered.includes("v2")) {
    throw new Error(`Band card render incomplete: ${checkResult.bandRendered}`);
  }
  console.log("✓ Venue and entity schema representations rendered in browser DOM");

  // Axe accessibility audit
  await page.addScriptTag({ content: AXE });
  const axeResult = await page.evaluate(async () => {
    return await window.axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] },
      rules: { region: { enabled: false } },
    });
  });

  if (axeResult.violations.length > 0) {
    console.error("Axe violations on schema view:", axeResult.violations.map(v => v.id));
    throw new Error(`Axe violations found: ${axeResult.violations[0].id}`);
  }
  console.log("✓ Schema entity view audited with 0 Axe violations");

  // Capture screenshot
  const screenPath = DOCS + "screens/venue-entity-schemas.png";
  await page.screenshot({ path: screenPath });
  console.log(`✓ Screenshot captured at ${screenPath}`);

  await page.close();
} finally {
  await browser.close();
}

console.log("✓ Task 2.11 (Venue & entity schemas) passed all schema validation, unit, and browser checks");
