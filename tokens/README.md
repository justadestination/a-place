# NightCal tokens

These files are the single source of truth for every visual value.

| File | What | Edit? |
|---|---|---|
| `base.json` | Primitives: palette, type, space, radius, size, motion, density, z | yes |
| `themes/light.json`, `themes/dark.json` | Semantic tokens (`color.*`, `shadow.*`). Values are literals or `{palette.x.y}` references. Both files have the same keys. | yes |
| `pairs.json` | Every fg/bg pairing components use, with its WCAG minimum | yes, whenever a component pairs two colours |
| `build.py` | Generates the outputs and fails on any contrast miss | rarely |
| `dist/tokens.json` | Flat `--nc-*` → value per theme | generated |
| `dist/contrast.md` | The contrast report | generated |
| `theme.schema.json` | JSON Schema for agent theme specs | generated |
| `../web/css/tokens.css`, `../web/js/core/tokens.js` | Runtime outputs | generated |

`python3 tokens/build.py` builds everything; `--check` only checks.

## Naming

CSS variable = `--nc-` + the token's path joined with `-`:

* `palette.amber.400` → `--nc-palette-amber-400`
* `font.size.lg` → `--nc-font-size-lg`
* `color.text-muted` → `--nc-color-text-muted`

Spacing tokens are emitted as `calc(<value> * var(--nc-density))`, and durations as `calc(<value> * var(--nc-motion-scale))`. That's how the density and motion knobs reach every component with no component code.

Semantic tokens that reference a primitive are emitted as `var(--nc-palette-…)`. Overriding a palette entry at runtime therefore recolours every role built on it.

## Themes in CSS

* `:root` holds light.
* `@media (prefers-color-scheme: dark) :root:not([data-theme="light"])` and `:root[data-theme="dark"]` hold dark.
* The theme API's overrides are written with higher specificity (see `web/js/core/theme.js`).
