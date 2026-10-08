# NightCal front-end (`web/`): read this first

This is the visual layer for NightCal and the AVR+JIT zine: tokens, themes, components, embed routes, a 2D site and a 3D/AR preview. It is plain ES modules and CSS, **with no framework and no runtime build step**. Python and Node scripts only generate static files and run checks. The backend (`shadenet/nightcal`) is unchanged; this layer only reads `GET /api/model`.

```
tokens/                 (repo root) token sources -> generated CSS/JS, contrast gate, theme schema
web/
  site.json             name, place, origin (used in headings and social metadata)
  routes.json           full pages; embeds are discovered from components/
  components/<name>/    <name>.js  <name>.css  README.md   <- one folder per component
  js/core/              theme API, theme boot, embed bridge, share, dom helper
  js/data/              backend adapter (calendar.js) + renderer-neutral scene models
  js/layout/force.js    deterministic force layout (2D and 3D)
  js/pages/             one module per page, plus embed.js for every /embed/* route
  js/render3d/          three.js renderer (lazy, /3d/ only)
  css/                  tokens.css (generated), base.css, pages.css, nightcal.css (generated bundle)
  data/                 sample-model.json (API fallback), zine.json (generated)
  embed.js              host-page loader for embeds
  tools/                build_pages.py, build_zine.py, serve.py, og.mjs, vendor.mjs, shot.mjs
  tests/run.mjs         every route x viewport x theme: axe, targets, focus, theme API, embeds, LCP
  deploy/               Caddy snippet
```

## Run it

Start each of these from the repo root:

```sh
# 1. the existing API (unchanged)
NIGHTCAL_DB=shadenet/data/shadenet.db python3 -m shadenet.nightcal.server        # :8765
# 2. the front-end, with /api/* proxied to it
cd web && npm install && npm run build && npm run serve                          # :8080
# 3. checks (needs both servers running)
npm test                      # full suite, including throttled LCP and screenshots
node tests/run.mjs --quick    # skip LCP and screenshots
```

* If the API is down, the site falls back to `data/sample-model.json`; the footer says so.
* **The API server writes to its database on every request** (`cite_closures`). For local work, point `NIGHTCAL_DB` at a copy so the repo's `shadenet.db` stays clean.
* `npm run build` runs `tokens/build.py`, `tools/build_zine.py` and `tools/build_pages.py`. Run `npm run og` (with the server up) after changing titles or components, and `npm run vendor` after bumping `three`.

## Five rules that keep the system intact

1. **Tokens only.** No hex, `rgb()` or `px` in component CSS (the test fails on them). If you need a value, add a token to `tokens/base.json` (primitive) or to both `tokens/themes/*.json` (semantic).
2. **Contrast is a build gate.** Every colour pairing you use belongs in `tokens/pairs.json`. `tokens/build.py` fails below AA, and the runtime theme API refuses overrides that would break a pair.
3. **The adapter is the only thing that knows the backend.** Components take scene models (`js/data/scene.js`, `js/data/graph.js`), never raw API JSON.
4. **Every component has an embed.** A folder with `<name>.js` that exports `meta` and `embed()` automatically gets `/embed/<name>/`, social metadata, a gallery entry on `/system/`, and test coverage.
5. **One primary action per screen. 44px targets. Text 13px or larger.** The tests check the last two; reviewers check the first.

## Add a component

1. Create `components/<name>/` (lowercase-hyphenated; the name must match the folder).
2. `<name>.js` exports:
   ```js
   export function myThing(sceneOrRecord, options) { return h("div.nc-my-thing", {}, …); } // pure: data in, element out
   export const meta = {
     name: "my-thing",                    // = folder name
     title: "My thing",
     summary: "One sentence. Used for the embed's <title>, og:description and the gallery.",
     params: { id: "what the query param does" },   // string values only
   };
   export async function embed(params, ctx) {        // ctx: { calendar(), zine(), select(kind, id, extra), params }
     const model = await ctx.calendar();
     return myThing(…);
   }
   ```
   * Fire interactions as `nc-select` (`{ kind, id }`) or `nc-<verb>` CustomEvents with `emit()` from `js/core/dom.js`. Pages and `embed.js` forward them; the frame bridge reports `select` to the host.
3. `<name>.css`: class prefix `.nc-<name>`, `var(--nc-…)` only. Use container queries (`@container`) rather than media queries, so the component adapts to the frame it sits in.
4. `README.md`: use, embed params, events, accessibility, rules. Copy a sibling's layout.
5. `npm run build && npm run og && npm test`. The new route is checked at 2 viewports × 2 themes automatically.

## Add a theme

* **For one reader, at runtime** (Steward): emit a spec and call `NightCal.theme.apply(spec)`. See `docs/THEME_API.md`. No code changes.
* **A new canonical theme** (for example high-contrast):
  1. Copy `tokens/themes/light.json` to `tokens/themes/<name>.json`. Keep **every** key (the build fails on missing or extra keys) and change the values.
  2. Run `python3 tokens/build.py`. It must report every pair passing.
  3. Light and dark are the shipped CSS blocks. To expose a third canonical theme, add a `:root[data-theme="<name>"]` block in `tokens/build.py` (next to the dark one) and allow the name in `theme.js` `validate()` and `theme-boot.js`.
* **Change a brand colour everywhere:** change the primitive in `tokens/base.json` (for example `palette.amber.400`). Every semantic token built on it follows.

## Add an embed route

Every component already has one. For an embed that composes several components (for example "this week + filters"), make it a component of its own: a folder whose `embed()` assembles the others. Don't hand-write HTML under `embed/`; `tools/build_pages.py` overwrites it.

## Add a page

Add an entry to `routes.json` (`path`, `title`, `description`, `module`, `og`) and create `js/pages/<page>.js`. It should render `siteHeader()`, a `<main id="main" class="nc-container nc-page">`, and `siteFooter()`. Then run `npm run build && npm run og`.

## What not to touch

* Anything under `shadenet/`. That's the backend's (non-goal: no backend or data changes).
* Generated files: `css/tokens.css`, `css/nightcal.css`, `js/core/tokens.js`, `js/core/site.js`, `components/index.json`, every `index.html`, `data/zine.json`, `og/*.png`, `tokens/dist/*`, `tokens/theme.schema.json`.
* `vendor/`: regenerate with `npm run vendor`.

## Docs

* `docs/AUDIT.md`: the legacy page's problems, with screenshots
* `docs/THEME_API.md`: theme spec, runtime hooks, embed protocol
* `docs/ARCHITECTURE_2D_3D.md`: the shared data layer and the AR scene graph
* `docs/ACCESSIBILITY.md`: the WCAG 2.2 AA audit of this layer
* `docs/PERFORMANCE.md`: the budget and how it is measured
* `docs/LANDING_OPTIONS.md`: three front doors, waiting on the owner's choice
