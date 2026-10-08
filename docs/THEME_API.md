# Theme API

This is for a Steward agent (or any host) that restyles NightCal for one reader. Everything visual is a token. A theme is a JSON object that overrides tokens and sets four knobs. Changes apply live, with no reload and no flash.

* Runtime: `web/js/core/theme.js`, exposed as `window.NightCal.theme` on every page and embed.
* Schema: [`tokens/theme.schema.json`](../tokens/theme.schema.json). It is generated, and lists every valid token name.
* Token names: `--nc-<name>` in `web/css/tokens.css`. In a spec, write the name without the prefix, using `-` or `.` as the separator (`color-accent` and `color.accent` are the same key).

## The spec

```json
{
  "version": 1,
  "name": "steward/large-print-dark",
  "scheme": "dark",
  "textScale": 1.5,
  "density": "spacious",
  "motion": "reduce",
  "tokens":  { "radius.md": "4px" },
  "schemes": {
    "dark":  { "color.accent": "#FF9E5E", "color.accent-text": "#FFB98C" },
    "light": { "color.accent": "#FFB070" }
  }
}
```

| Field | Values | Effect |
|---|---|---|
| `scheme` | `system` (default), `light`, `dark` | Which canonical theme is the base |
| `textScale` | 1–2 (clamped) | Multiplies the root font size. Every size is in rem, so all text scales. The reader's browser setting still applies underneath. |
| `density` | `compact` (0.8), `comfortable` (1), `spacious` (1.25), or a number from 0.75 to 1.5 | Multiplies every `space-*` token. **Touch targets never shrink below 44px.** |
| `motion` | `system`, `reduce`, `full` | `reduce` sets `--nc-motion-scale: 0`, so every duration becomes 0ms |
| `tokens` | `{ name: value }` | Overrides that apply in every scheme |
| `schemes.light` / `schemes.dark` | `{ name: value }` | Overrides for one scheme only. These win over `tokens`. |

Overriding a **palette** token (`palette.amber.400`) recolours every semantic token built on it. Overriding a **semantic** token (`color.accent`) changes just that role. Agents should usually override semantic tokens.

## Calls

```js
const T = window.NightCal.theme;          // or: import Theme from "/js/core/theme.js"

T.apply(spec)                              // merge onto the current spec, apply, save
T.apply(spec, { merge: false })            // replace the current spec
T.apply(spec, { persist: false })          // apply for this page view only (embeds do this)
T.apply(spec, { enforceContrast: false })  // allow AA failures (they are still reported)

T.setTextScale(1.25)
T.setDensity("compact")                    // or a number
T.setScheme("dark")                        // "light" | "dark" | "system"
T.setMotion("reduce")
T.setToken("color.accent", "#FF7A00")      // every scheme
T.setToken("color.accent", "#FF7A00", "dark")
T.reset()                                  // back to canonical

T.get()            // current spec
T.validate(spec)   // { spec, errors }; never throws
T.tokenNames()     // every valid key
T.read("color.text")   // computed value as the page sees it now (for canvas/WebGL)
T.activeScheme()       // "light" | "dark"
T.reducedMotion()      // boolean
T.subscribe(fn)        // fn(result) after every apply; returns an unsubscribe function
document.addEventListener("nightcal:themechange", e => e.detail)  // same result object
```

`apply` returns this, and never throws:

```json
{
  "spec":     { "...": "what is now applied" },
  "errors":   ["tokens: unknown token \"color.brand\""],
  "rejected": [{ "token": "color-text-muted", "scheme": "light", "reason": "text-muted on bg would be 1.50:1, needs 4.5:1" }],
  "failures": []
}
```

### Contrast is enforced

Before applying, the API checks every pair in [`tokens/pairs.json`](../tokens/pairs.json) (the same list the build uses) in both schemes. **Any override that would push a pair below its WCAG 2.2 AA minimum is dropped and reported in `rejected`; the rest of the spec still applies.** An agent can't make the site unreadable by accident. It can pass `enforceContrast: false` to experiment, and the failures still come back in `failures`.

Values are also sanitised. Colour tokens must parse as colours. Values containing `; { } < >`, `url(` or `@import` are refused.

## No flash, no reload

* `apply` writes one `<style id="nc-theme-overrides">` (selectors out-rank the base theme blocks) and sets `data-theme`, `data-density`, `data-motion` and `--nc-text-scale` on `<html>`.
* With `persist` it saves `{ ...spec, css }` to `localStorage["nightcal.theme.v1"]`. Every page inlines `theme-boot.js` in `<head>`, before the stylesheet. That script restores the attributes and the override CSS synchronously, so the first paint already uses the reader's theme. Tested: `tests/run.mjs` reloads after `apply` and checks the first-paint state.
* If storage is blocked (private mode, third-party iframe), the theme still applies for the current page view.

## Examples a Steward can copy

**Low vision, large print:**
```json
{ "version": 1, "name": "large-print", "textScale": 1.5, "density": "spacious" }
```

**Dark, reduced motion (also for migraine or vestibular needs):**
```json
{ "version": 1, "scheme": "dark", "motion": "reduce" }
```

**Higher contrast than AA, light:**
```json
{ "version": 1, "scheme": "light",
  "schemes": { "light": { "color.text-muted": "#2A2825", "color.border": "#57534A", "color.border-strong": "#121214" } } }
```

**A reader's own accent colour (it is checked for contrast):**
```json
{ "version": 1, "tokens": { "color.accent": "#7FD1AE" } }
```

**Dense, for a power user on a desktop:**
```json
{ "version": 1, "density": "compact", "textScale": 1 }
```

Try any of these live on `/system/#theme-api`.

## Embeds

Each component has a standalone route, `/embed/<name>/`, with no page chrome. The quickest setup is the loader:

```html
<div data-nightcal="calendar-week"
     data-params="scope=nights"
     data-theme='{"scheme":"dark","textScale":1.25}'></div>
<script src="https://nightcal.justadestination.com/embed.js" async></script>
```

The loader lazy-loads an iframe and resizes it to fit its content. It passes `scheme`, `textScale` and `density` in the query string, so the first paint inside the frame already matches. It sends any token overrides as a `theme` message once the frame is ready. The element fires `nightcal:ready`, `nightcal:resize`, `nightcal:select` and `nightcal:themechange`, and gets `el.nightcal.theme(spec)`, `.textScale(n)`, `.density(d)` and `.scheme(s)`.

### Raw postMessage protocol

You can also use a bare `<iframe src=".../embed/day-agenda/?date=2026-10-09&frameId=a1">`:

| Direction | Message |
|---|---|
| frame → host | `{ source: "nightcal", version: 1, frameId, type: "ready", route }` |
| frame → host | `{ ..., type: "resize", height }` whenever the content height changes |
| frame → host | `{ ..., type: "select", kind: "event" \| "day" \| "node" \| "filter", id, url?, label? }` |
| frame → host | `{ ..., type: "themechange", spec, rejected, errors }` |
| host → frame | `{ target: "nightcal", type: "theme", spec }` |
| host → frame | `{ target: "nightcal", type: "textScale" \| "density" \| "scheme", value }` |
| host → frame | `{ target: "nightcal", type: "ping" }` (the frame answers `ready`) |

* Inside a frame, theme messages are applied with `persist: false`. A host can't change the reader's saved preferences on nightcal itself.
* The frame posts to `"*"` because the messages carry no personal data. Hosts should check `event.source === iframe.contentWindow`. The loader does this.
* In list embeds (`day-agenda`, `calendar-week`, `event-row`), activating an event opens its card in a dialog inside the frame. Add `open=0` to `data-params` if the host wants to handle `select` itself.
