// Screenshot one route and print console errors.
//   node tools/shot.mjs /path/ out.png [mobile|desktop] [light|dark] [full]
import { launch, VIEWPORTS } from "./browser.mjs";

const [path = "/", out = "shot.png", vpName = "desktop", scheme = "light", full = ""] = process.argv.slice(2);
const base = process.env.BASE || "http://127.0.0.1:8080";
const browser = await launch();
const vp = VIEWPORTS[vpName];
const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height }, ...vp, colorScheme: scheme });
const errors = [];
page.on("console", m => { if (m.type() === "error" || m.type() === "warning") errors.push(`${m.type()}: ${m.text()}`); });
page.on("pageerror", e => errors.push(`pageerror: ${e.message}`));
page.on("requestfailed", r => errors.push(`requestfailed: ${r.url()} ${r.failure()?.errorText}`));
await page.goto(base + path, { waitUntil: "networkidle" });
await page.waitForTimeout(500);
await page.screenshot({ path: out, fullPage: full === "full" });
console.log(errors.length ? errors.join("\n") : "no console errors");
await browser.close();
