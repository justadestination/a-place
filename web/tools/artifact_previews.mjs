// Capture design-system/project/components/<Comp>/preview.html from the live
// embed routes: a static render of the real component, for the published
// design-system artifact (see design-system/README.md).
// Needs the dev server (python3 tools/serve.py) and the nightcal API, like og.mjs.
//   node tools/artifact_previews.mjs [--check]
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { launch } from "./browser.mjs";

const BASE = process.env.BASE || "http://127.0.0.1:8080";
const WEB = new URL("../", import.meta.url).pathname;
const OUT = new URL("../../design-system/project/components/", import.meta.url).pathname;
const check = process.argv.includes("--check");
const comps = JSON.parse(readFileSync(WEB + "components/index.json", "utf8"));
const GROUP = {
  button: "Actions", "share-button": "Actions", "kind-tag": "Content",
  "event-card": "Calendar", "event-row": "Calendar", "day-agenda": "Calendar", "calendar-week": "Calendar", "calendar-month": "Calendar", "filter-bar": "Calendar",
  "theme-controls": "Settings", "site-header": "Chrome", "site-footer": "Chrome",
  "zine-card": "Zine", "zine-reader": "Zine", "node-map": "Zine",
};
// Fixed params so previews don't change with the date they were captured.
// The artifact only loads CDN scripts and its own files, so the event card's
// external listing image is turned off.
const PARAMS = { "event-card": "image=0", "day-agenda": "date=2026-10-10", "calendar-week": "date=2026-10-10", "node-map": "node=note:late-show-review" };
const pascal = n => n.split("-").map(s => s[0].toUpperCase() + s.slice(1)).join("");

const browser = await launch();
const page = await browser.newPage({ viewport: { width: 760, height: 900 } });
const stale = [];
for (const c of comps) {
  if (!GROUP[c.name]) { console.warn(`no artifact group for ${c.name}; add it to GROUP`); stale.push(c.name); continue; }
  await page.goto(`${BASE}/embed/${c.name}/?${PARAMS[c.name] || ""}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(300);
  const { html, height } = await page.evaluate(() => {
    const root = document.querySelector(".nc-embed-root");
    root.querySelectorAll("h1.nc-sr-only").forEach(e => e.remove());
    return { html: root.innerHTML, height: Math.ceil(root.getBoundingClientRect().height) };
  });
  const doc = `<!-- @dsCard group="${GROUP[c.name]}" height=${Math.min(1400, Math.max(80, height + 24))} subtitle="/embed/${c.name}/" -->
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>${c.title}</title>
<style>body{margin:0;background:var(--nc-color-bg);color:var(--nc-color-text);font-family:var(--nc-font-family-sans)}</style>
</head>
<body>
<!-- Static render of the live component at /embed/${c.name}/ (captured from the real module; interactive version: the embed route). -->
<div class="nc-embed-root" style="padding:12px">${html}</div>
</body>
</html>
`;
  const file = `${OUT}${pascal(c.name)}/preview.html`;
  const current = existsSync(file) ? readFileSync(file, "utf8") : null;
  if (current !== doc) {
    stale.push(pascal(c.name));
    if (!check) { mkdirSync(`${OUT}${pascal(c.name)}`, { recursive: true }); writeFileSync(file, doc); }
  }
}
await browser.close();
if (check && stale.length) { console.error(`previews differ from the live components: ${stale.join(", ")}`); process.exit(1); }
console.log(stale.length ? `${check ? "differ" : "updated"}: ${stale.join(", ")}` : "previews up to date");
