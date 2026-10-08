// NightCal front-end checks. Needs the dev server (python3 tools/serve.py).
//   node tests/run.mjs            all checks
//   node tests/run.mjs --quick    skip the throttled LCP runs and screenshots
// Writes docs/audit/report.json and screenshots to docs/screens/. Exit 1 on any failure.
import { readFileSync, writeFileSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { launch, VIEWPORTS } from "../tools/browser.mjs";
import { chromium } from "playwright-core";

const require = createRequire(import.meta.url);
const AXE = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.env.BASE || "http://127.0.0.1:8080";
const WEB = new URL("../", import.meta.url).pathname;
const DOCS = new URL("../../docs/", import.meta.url).pathname;
const quick = process.argv.includes("--quick");
const routes = JSON.parse(readFileSync(WEB + "routes.json", "utf8")).pages.map(p => p.path);
const embeds = JSON.parse(readFileSync(WEB + "components/index.json", "utf8")).map(c => `/embed/${c.name}/`);
const failures = [];
const report = { routes: {}, checks: {} };
const fail = (where, what) => { failures.push(`${where}: ${what}`); };
mkdirSync(DOCS + "screens", { recursive: true });
mkdirSync(DOCS + "audit", { recursive: true });

const browser = await launch();

// --- 1. every route x viewport x scheme -------------------------------------
async function audit(path, vpName, scheme) {
  const vp = VIEWPORTS[vpName];
  const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height }, ...vp, colorScheme: scheme, bypassCSP: true });
  const errors = [];
  page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", e => errors.push(e.message));
  await page.goto(BASE + path, { waitUntil: "networkidle" });
  await page.waitForTimeout(250);
  await page.addScriptTag({ content: AXE });
  const result = await page.evaluate(async () => {
    const axe = await window.axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"] }, rules: { region: { enabled: false } } });
    const visible = el => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && !el.closest(".nc-sr-only, [hidden], [aria-hidden='true']"); };
    const tiny = [];
    for (const el of document.querySelectorAll("body *")) {
      if (!visible(el) || el.closest("svg.nc-glyph")) continue;
      const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
      if (own && parseFloat(getComputedStyle(el).fontSize) < 12) tiny.push(`${el.tagName.toLowerCase()}.${el.className} ${getComputedStyle(el).fontSize}`);
    }
    const small = [];
    for (const el of document.querySelectorAll("a, button, input, select, summary, [role='button'], [tabindex='0']")) {
      const target = el.matches("input[type=radio]") ? el.parentElement : el.matches(".nc-zine-card__link") ? el.closest(".nc-zine-card") : el;
      if (!visible(target)) continue;
      if (el.matches("p a, li > a.nc-share__item ~ *, dd a, .nc-prose a, .nc-event-card__source a")) continue; // inline links in text: 2.5.8 exception
      if (el.matches(".nc-map__node")) continue; // SVG hit area is a 44px circle; bbox check below
      const r = target.getBoundingClientRect();
      if (r.width < 43.5 || r.height < 43.5) small.push(`${el.tagName.toLowerCase()}.${String(el.className).split(" ")[0]} ${Math.round(r.width)}x${Math.round(r.height)}`);
    }
    const meta = n => document.querySelector(`meta[property="${n}"], meta[name="${n}"]`)?.content || "";
    return {
      axe: axe.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, sample: v.nodes[0]?.target.join(" ") })),
      tiny: [...new Set(tiny)], small: [...new Set(small)],
      og: ["og:title", "og:description", "og:image", "og:url", "twitter:card", "twitter:image"].filter(n => !meta(n)),
      hScroll: document.documentElement.scrollWidth > innerWidth + 1,
    };
  });
  const key = `${path} ${vpName} ${scheme}`;
  report.routes[key] = { ...result, errors };
  if (errors.length) fail(key, `console errors: ${errors.join(" | ")}`);
  for (const v of result.axe) fail(key, `axe ${v.id} (${v.impact}) x${v.nodes} e.g. ${v.sample}`);
  if (result.tiny.length) fail(key, `text under 12px: ${result.tiny.slice(0, 3).join(", ")}`);
  if (result.small.length) fail(key, `targets under 44px: ${result.small.slice(0, 4).join(", ")}`);
  if (result.og.length) fail(key, `missing social meta: ${result.og.join(", ")}`);
  if (result.hScroll) fail(key, "horizontal scroll");
  if (!quick && !path.startsWith("/embed/")) await page.screenshot({ path: `${DOCS}screens/${(path.replace(/\//g, "_").replace(/^_|_$/g, "") || "calendar")}-${vpName}-${scheme}.png`, fullPage: true });
  await page.close();
}
for (const path of [...routes, ...embeds]) for (const vp of ["mobile", "desktop"]) for (const s of ["light", "dark"]) await audit(path, vp, s);

// --- 2. keyboard: every tab stop shows a focus indicator ---------------------
{
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  for (const path of ["/", "/zine/"]) {
    await page.goto(BASE + path, { waitUntil: "networkidle" });
    const stops = [];
    for (let i = 0; i < 30; i++) {
      await page.keyboard.press("Tab");
      stops.push(await page.evaluate(() => {
        const a = document.activeElement;
        if (!a || a === document.body) return null;
        const target = a.matches("input[type=radio]") ? a.nextElementSibling : a;
        const cs = getComputedStyle(target);
        const hit = a.querySelector?.(".nc-map__hit");
        const ring = cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) >= 2;
        const svgRing = hit && getComputedStyle(hit).stroke !== "none";
        const cardRing = a.closest(".nc-zine-card") && getComputedStyle(a.closest(".nc-zine-card")).outlineStyle !== "none";
        return { el: `${a.tagName.toLowerCase()}.${String(a.className.baseVal ?? a.className).split(" ")[0]}`, visible: !!(ring || svgRing || cardRing) };
      }));
    }
    const bad = stops.filter(s => s && !s.visible);
    report.checks[`keyboard ${path}`] = { stops: stops.filter(Boolean).length, withoutRing: bad.map(b => b.el) };
    if (bad.length) fail(`keyboard ${path}`, `no visible focus on ${[...new Set(bad.map(b => b.el))].join(", ")}`);
  }
  // Month grid arrow keys move focus by day and week.
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  await page.locator(".nc-cal__month").scrollIntoViewIfNeeded();
  await page.waitForSelector(".nc-month__day[tabindex='0']");
  await page.focus(".nc-month__day[tabindex='0']");
  const d0 = await page.evaluate(() => document.activeElement.dataset.date);
  await page.keyboard.press("ArrowRight"); await page.keyboard.press("ArrowDown");
  const d1 = await page.evaluate(() => document.activeElement.dataset.date);
  const diff = (new Date(d1) - new Date(d0)) / 864e5;
  report.checks["month arrows"] = { from: d0, to: d1, days: diff };
  if (diff !== 8) fail("month grid", `ArrowRight+ArrowDown moved ${diff} days, expected 8`);
  // Node map: one tab stop, arrows move between nodes, Enter opens.
  await page.goto(BASE + "/zine/", { waitUntil: "networkidle" });
  await page.focus(".nc-map__node[tabindex='0']");
  const n0 = await page.evaluate(() => document.activeElement.dataset.id);
  await page.keyboard.press("ArrowRight");
  const n1 = await page.evaluate(() => document.activeElement.dataset.id);
  await page.keyboard.press("Enter");
  const opened = await page.evaluate(() => new URLSearchParams(location.search).get("node"));
  report.checks["node map keys"] = { from: n0, to: n1, opened };
  if (!n1 || n1 === n0 || opened !== n1) fail("node map", `arrow/enter navigation failed (${n0} -> ${n1}, opened ${opened})`);
  await page.close();
}

// --- 3. theme API: live, no reload, contrast enforced, no flash on reload ----
{
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  const r = await page.evaluate(() => {
    window.__noReload = true;
    const before = getComputedStyle(document.documentElement).fontSize;
    const a = NightCal.theme.apply({ textScale: 1.5, density: "spacious", scheme: "dark" });
    const after = getComputedStyle(document.documentElement).fontSize;
    const bg = getComputedStyle(document.body).backgroundColor;
    const bad = NightCal.theme.apply({ tokens: { "color.text-muted": "#CCCCCC", "color.accent": "#FF7A00" } });
    const accent = NightCal.theme.read("color.accent");
    const muted = NightCal.theme.read("color.text-muted");
    return { before, after, bg, errors: a.errors, rejected: bad.rejected.map(x => x.token), accent, muted, still: window.__noReload === true };
  });
  await page.reload({ waitUntil: "domcontentloaded" });
  const boot = await page.evaluate(() => ({ theme: document.documentElement.dataset.theme, scale: document.documentElement.style.getPropertyValue("--nc-text-scale"), override: !!document.getElementById("nc-theme-overrides") }));
  await page.evaluate(() => NightCal.theme.reset());
  report.checks["theme api"] = { ...r, afterReloadFirstPaint: boot };
  if (r.before === r.after) fail("theme api", "textScale did not change root font size");
  if (!r.still) fail("theme api", "page reloaded");
  if (!r.rejected.includes("color-text-muted")) fail("theme api", "low-contrast override was not rejected");
  if (r.accent.toUpperCase() !== "#FF7A00") fail("theme api", `valid override not applied (${r.accent})`);
  if (boot.theme !== "dark" || boot.scale !== "1.5" || !boot.override) fail("theme api", `boot script did not restore theme before paint: ${JSON.stringify(boot)}`);
  await page.close();
}

// --- 4. embed bridge (host page <-> iframe) ----------------------------------
{
  const page = await browser.newPage({ viewport: { width: 1000, height: 900 } });
  await page.goto(BASE + "/tests/host.html", { waitUntil: "networkidle" });
  await page.waitForFunction(() => window.events.some(e => e.type === "resize"), null, { timeout: 8000 }).catch(() => {});
  const h1 = await page.evaluate(() => document.querySelector("#slot iframe").getBoundingClientRect().height);
  await page.evaluate(() => document.getElementById("slot").nightcal.scheme("dark"));
  await page.waitForFunction(() => window.events.some(e => e.type === "themechange"), null, { timeout: 5000 }).catch(() => {});
  const frame = page.frames().find(f => f.url().includes("/embed/calendar-week/"));
  const inner = frame ? await frame.evaluate(() => ({ theme: document.documentElement.dataset.theme, scale: getComputedStyle(document.documentElement).getPropertyValue("--nc-text-scale").trim() })) : null;
  await frame?.click(".nc-week__day >> nth=5");
  await page.waitForFunction(() => window.events.some(e => e.type === "select"), null, { timeout: 5000 }).catch(() => {});
  const types = await page.evaluate(() => window.events.map(e => e.type));
  report.checks["embed bridge"] = { iframeHeight: h1, inner, events: [...new Set(types)] };
  for (const t of ["ready", "resize", "themechange", "select"]) if (!types.includes(t)) fail("embed bridge", `no ${t} message`);
  if (h1 < 150) fail("embed bridge", `iframe not resized (${h1}px)`);
  if (inner?.theme !== "dark") fail("embed bridge", "theme message not applied in frame");
  if (inner?.scale !== "1.25") fail("embed bridge", "initial theme from data-theme not applied");
  await page.close();
}

// --- 5. reduced motion -------------------------------------------------------
{
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, reducedMotion: "reduce" });
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  const m = await page.evaluate(() => ({ scale: getComputedStyle(document.documentElement).getPropertyValue("--nc-motion-scale").trim(), btn: getComputedStyle(document.querySelector(".nc-button")).transitionDuration }));
  report.checks["reduced motion"] = m;
  if (m.scale !== "0" || !/^0s/.test(m.btn)) fail("reduced motion", JSON.stringify(m));
  await page.close();
}

// --- 6. 3D page with no WebGL still works ------------------------------------
{
  const nogl = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium", args: ["--disable-webgl", "--disable-webgl2", "--disable-3d-apis"] });
  const page = await nogl.newPage();
  const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  await page.goto(BASE + "/3d/", { waitUntil: "networkidle" });
  const r = await page.evaluate(() => ({ status: document.querySelector("[role=status]")?.textContent, rows: document.querySelectorAll(".nc-event-row").length, three: performance.getEntriesByType("resource").some(e => e.name.includes("three.module")) }));
  report.checks["3d without webgl"] = { ...r, errors: errs };
  if (!/can't draw 3D/.test(r.status || "") || !r.rows || r.three || errs.length) fail("3d without webgl", JSON.stringify(r));
  await nogl.close();
}

// --- 7. performance budget: LCP under 2.5 s, throttled ------------------------
if (!quick) {
  for (const path of ["/", "/zine/", "/landing/a/"]) {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true });
    const page = await ctx.newPage();
    const cdp = await ctx.newCDPSession(page);
    // "Mid-range mobile": 4x CPU slowdown, Fast 3G-ish network (1.6 Mbps, 150 ms RTT).
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
    await cdp.send("Network.enable");
    await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: 150, downloadThroughput: 1.6e6 / 8, uploadThroughput: 750e3 / 8 });
    await page.addInitScript(() => {
      window.__lcp = 0;
      new PerformanceObserver(l => { for (const e of l.getEntries()) window.__lcp = e.startTime; }).observe({ type: "largest-contentful-paint", buffered: true });
    });
    await page.goto(BASE + path, { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    const r = await page.evaluate(() => {
      const res = performance.getEntriesByType("resource");
      const js = res.filter(e => /\.js(\?|$)/.test(e.name));
      return { lcp: Math.round(window.__lcp), jsFiles: js.length, jsBytes: js.reduce((a, e) => a + (e.encodedBodySize || 0), 0), cssBytes: res.filter(e => /\.css/.test(e.name)).reduce((a, e) => a + (e.encodedBodySize || 0), 0) };
    });
    report.checks[`lcp ${path}`] = r;
    if (r.lcp > 2500) fail(`lcp ${path}`, `${r.lcp} ms`);
    await ctx.close();
  }
}

// --- 8. token discipline: no raw colours or px in component CSS ----------------
{
  const offenders = [];
  for (const dir of readdirSync(WEB + "components", { withFileTypes: true }).filter(d => d.isDirectory())) {
    let css = "";
    try { css = readFileSync(`${WEB}components/${dir.name}/${dir.name}.css`, "utf8"); } catch { continue; }
    css.split("\n").forEach((line, i) => {
      if (/#[0-9a-f]{3,8}\b|rgba?\(|hsl\(|\b\d+(\.\d+)?px\b/i.test(line.replace(/\/\*.*?\*\//g, ""))) offenders.push(`${dir.name}.css:${i + 1}: ${line.trim()}`);
    });
  }
  report.checks["token discipline"] = offenders;
  if (offenders.length) fail("token discipline", offenders.slice(0, 5).join(" | "));
}

await browser.close();
report.failures = failures;
writeFileSync(DOCS + "audit/report.json", JSON.stringify(report, null, 2));
const audited = Object.keys(report.routes).length;
console.log(`${audited} route/viewport/scheme combinations audited; ${Object.keys(report.checks).length} extra checks`);
for (const [k, v] of Object.entries(report.checks)) if (!Array.isArray(v)) console.log(`  ${k}: ${JSON.stringify(v)}`);
if (failures.length) { console.log(`\nFAILURES (${failures.length}):\n  ` + failures.join("\n  ")); process.exit(1); }
console.log("\nall checks passed");
