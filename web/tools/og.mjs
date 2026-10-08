// Generate Open Graph / Twitter card images (1200x630) for every route.
//   pages  -> a branded title card (tools/og.html)
//   embeds -> a real render of the embed route, so the preview shows the component
// Needs the dev server: python3 tools/serve.py   then   node tools/og.mjs
import { readFileSync } from "node:fs";
import { launch } from "./browser.mjs";

const base = process.env.BASE || "http://127.0.0.1:8080";
const web = new URL("../", import.meta.url).pathname;
const site = JSON.parse(readFileSync(web + "site.json", "utf8"));
const routes = JSON.parse(readFileSync(web + "routes.json", "utf8")).pages;
const comps = JSON.parse(readFileSync(web + "components/index.json", "utf8"));
const EYEBROW = { calendar: site.place, zine: `The ${site.zineName} zine`, ar: "AR preview", system: "Design system", landing: "For the owner" };

const browser = await launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, colorScheme: "dark" });
for (const r of routes) {
  const parts = r.title.split(" — ");
  let title = parts[0] === site.name && parts[1] ? parts[1] : parts[0];
  title = title[0].toUpperCase() + title.slice(1);
  const q = new URLSearchParams({ eyebrow: EYEBROW[r.og] || EYEBROW[r.og.split("-")[0]] || site.place, title, name: site.name, desc: site.place });
  await page.goto(`${base}/tools/og.html?${q}`, { waitUntil: "networkidle" });
  await page.screenshot({ path: `${web}og/${r.og}.png` });
  console.log(`og/${r.og}.png`);
}
const light = await browser.newPage({ viewport: { width: 1200, height: 630 }, colorScheme: "light" });
for (const c of comps) {
  await light.goto(`${base}/embed/${c.name}/`, { waitUntil: "networkidle" });
  await light.waitForTimeout(300);
  await light.screenshot({ path: `${web}og/embed-${c.name}.png` });
  console.log(`og/embed-${c.name}.png`);
}
await browser.close();
