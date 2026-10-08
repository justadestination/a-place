// Screenshot + axe scan of the legacy calendar page (shadenet/nightcal/static/index.html).
// Run against a live nightcal server:  node tools/audit_legacy.mjs http://127.0.0.1:8765/
// Writes PNGs and axe-legacy.json into docs/audit/.
import { mkdirSync, writeFileSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { launch, VIEWPORTS } from "./browser.mjs";

const require = createRequire(import.meta.url);
const AXE = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const url = process.argv[2] || "http://127.0.0.1:8765/";
const out = new URL("../../docs/audit/", import.meta.url).pathname;
mkdirSync(out, { recursive: true });

const browser = await launch();
const report = {};
for (const [name, vp] of Object.entries(VIEWPORTS)) {
  const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height }, ...vp });
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${out}legacy-${name}.png`, fullPage: true });

  // Open the selected day the way a reader would, then capture it.
  const day = page.locator(".day.is-selected, .day.is-today").first();
  if (await day.count()) {
    await day.click({ force: true }).catch(() => {});
    await page.waitForTimeout(600);
    await page.screenshot({ path: `${out}legacy-${name}-open-day.png`, fullPage: false });
  }

  // Keyboard: where does focus go after 6 tabs, and is it visible?
  await page.keyboard.press("Escape").catch(() => {});
  const stops = [];
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press("Tab");
    stops.push(await page.evaluate(() => {
      const a = document.activeElement;
      if (!a) return null;
      const r = a.getBoundingClientRect();
      return { tag: a.tagName, cls: a.className && String(a.className).slice(0, 40), label: (a.getAttribute("aria-label") || a.textContent || "").trim().slice(0, 40), w: Math.round(r.width), h: Math.round(r.height) };
    }));
  }

  await page.addScriptTag({ content: AXE });
  const axe = await page.evaluate(async () => {
    const r = await window.axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"] } });
    return r.violations.map(v => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length, sample: v.nodes.slice(0, 3).map(n => n.target.join(" ")) }));
  });

  // Text smaller than 12px that is actually rendered.
  const tiny = await page.evaluate(() => {
    const seen = new Map();
    for (const el of document.querySelectorAll("body *")) {
      if (!el.childNodes.length) continue;
      const hasText = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
      if (!hasText) continue;
      const cs = getComputedStyle(el);
      const px = parseFloat(cs.fontSize);
      if (px > 0 && px < 12 && cs.visibility !== "hidden" && cs.display !== "none") {
        const key = `${el.tagName.toLowerCase()}.${String(el.className).split(" ")[0]} ${px}px`;
        seen.set(key, (seen.get(key) || 0) + 1);
      }
    }
    return [...seen].map(([k, n]) => `${k} ×${n}`);
  });

  // Targets under 44px.
  const small = await page.evaluate(() => [...document.querySelectorAll("button, a, [tabindex]")]
    .map(el => { const r = el.getBoundingClientRect(); return { cls: String(el.className).split(" ")[0] || el.tagName, w: Math.round(r.width), h: Math.round(r.height) }; })
    .filter(t => t.w > 0 && (t.w < 44 || t.h < 44))
    .reduce((acc, t) => { const k = `${t.cls} ${t.w}×${t.h}`; acc[k] = (acc[k] || 0) + 1; return acc; }, {}));

  report[name] = { axe, tabStops: stops, textUnder12px: tiny, targetsUnder44px: small };
  await page.close();
}
await browser.close();
writeFileSync(`${out}axe-legacy.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(Object.fromEntries(Object.entries(report).map(([k, v]) => [k, { axe: v.axe.map(a => `${a.id}(${a.nodes})`), tiny: v.textUnder12px.length, small: Object.keys(v.targetsUnder44px).length }])), null, 1));
