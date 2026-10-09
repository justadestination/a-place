# Performance budget

**Target: Largest Contentful Paint under 2.5 s on a mid-range phone.** That is the "good" threshold in Core Web Vitals.

## Budget

| Resource | Budget (gzip) | Now | How it is kept |
|---|---|---|---|
| HTML per route | 6 KB | ~5 KB raw, ~2 KB gzip | Static, generated; theme boot is inlined (~0.6 KB) |
| CSS, all routes | 15 KB | **9.1 KB** | One file (`css/nightcal.css`), cached with a content hash |
| JS before first render, `/` | 40 KB | **25.6 KB** (18 modules) | No framework; ES modules; whole static graph `modulepreload`ed |
| JS before first render, `/zine/` | 50 KB | **33.7 KB** (22 modules) | Same |
| JS, `/3d/` extra | 200 KB | **171 KB** (three.js, lazy) | Downloaded only after WebGL is detected, only on `/3d/` |
| Web fonts | 0 | 0 | System font stack: nothing to download, nothing to swap |
| Images | lazy | lazy | Listing images are `loading="lazy"`, with width and height set (no layout shift) |

The sizes are summed per module from `gzip -9`, so they are slightly pessimistic. Real compression of the whole transfer is better.

## Measured

`node web/tests/run.mjs` runs each route at a 390×844 phone viewport with **4× CPU slowdown** and **1.6 Mbps / 150 ms RTT** network throttling through Chrome DevTools Protocol. It reads LCP from `PerformanceObserver`.

| Route | LCP |
|---|---|
| `/` | ~0.9 s |
| `/landing/a/` | ~1.8 s |
| `/zine/` | ~2.0 s |

These are lab numbers from a local server in a container, not field data. The zine page is closest to the budget because its LCP waits for the graph data and layout.

## Rules that keep it there

1. **Static first paint.** `/` and `/zine/` ship real headings in their HTML, so there is something to paint before any script or data arrives.
2. **Code-split by route and by need.**
   * Each page imports only its components.
   * The month grid is `import()`ed when it scrolls near the viewport (IntersectionObserver plus `content-visibility: auto`).
   * The event card and dialog load on first open.
   * three.js loads only on `/3d/`.
   * Embeds load exactly one component.
3. **Preload the static module graph.** `tools/build_pages.py` walks each page's static imports and writes a `modulepreload` for every one, so the browser fetches them in parallel instead of one round-trip at a time.
4. **No theme flash (FOUC).** `theme-boot.js` is inlined before the stylesheet, and theme switches change CSS custom properties on `<html>`, so there is no reflow of new stylesheets. See [THEME_API.md](THEME_API.md).
5. **Graph layout runs once** before first paint (400 ticks, O(n²)). Measured on the container's CPU: **~40 ms for the current 31 nodes, ~360 ms for 300 nodes**. Before the zine passes ~150 nodes, move it to build time (it is deterministic, so precomputing positions into `zine.json` is a drop-in change) or to a worker.
6. **Caching.** `web/deploy/Caddyfile.snippet` serves the CSS and vendor files as immutable, and HTML as `no-cache`, compressed with zstd or gzip.

## When you add something

* Run `npm test` (from `web/`). The LCP check fails the build above 2.5 s.
* Anything below the fold goes behind `import()` or `content-visibility`.
* New third-party code needs a line in the table above and a reason.
