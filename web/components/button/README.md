# Button

The one control style. Primary is reserved for the single main action on a screen.

## Use

```js
import { button } from "/components/button/button.js";
const cta = button({ label: "Event page", variant: "primary", href: url, external: true });
```

## Embed

Standalone route: [`/embed/button/`](/embed/button/). Query parameters:

| Param | Meaning |
|---|---|
| `label` | text |
| `variant` | primary | secondary | ghost |
| `href` | optional URL |

Plus the shared embed params `scheme`, `textScale`, `density`, `frameId` (see `docs/THEME_API.md#embeds`).

```html
<div data-nightcal="button"></div>
<script src="https://nightcal.justadestination.com/embed.js" async></script>
```

## Events

Native click.

## Accessibility

- Renders `<a>` when given `href`, otherwise `<button type=button>`.
- `external: true` adds `target=_blank` and a visually hidden "(opens in a new tab)".
- `hideLabel: true` keeps the label as visually hidden text (for icon-only buttons).
- Minimum 44×44. `aria-pressed=true` and `aria-current=page` render as the selected style.

## Rules

- **Only one `primary` per screen.**
- Labels are verbs or destinations ("Event page", "Open the calendar"), never "Click here".
- Styling: `button.css`, tokens only (checked by `tests/run.mjs`, "token discipline").
