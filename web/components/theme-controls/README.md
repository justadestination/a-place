# Display settings

Theme, text size, spacing and motion, applied live through the public theme API.

## Use

```js
import { themeControls } from "/components/theme-controls/theme-controls.js";
panel.append(themeControls());
```

## Embed

Standalone route: [`/embed/theme-controls/`](/embed/theme-controls/). Query parameters:

| Param | Meaning |
|---|---|
| — | none |

Plus the shared embed params `scheme`, `textScale`, `density`, `frameId` (see `docs/THEME_API.md#embeds`).

```html
<div data-nightcal="theme-controls"></div>
<script src="https://nightcal.justadestination.com/embed.js" async></script>
```

## Events

None of its own; listen for `nightcal:themechange` on `document`.

## Accessibility

- Four radio groups with legends. Every change applies live and persists.

## Rules

- This is the reader's own UI for the same public API a Steward uses (`docs/THEME_API.md`). They stay in sync both ways.
- Styling: `theme-controls.css`, tokens only (checked by `tests/run.mjs`, "token discipline").
