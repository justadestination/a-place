# Site header

Wordmark, Calendar and Zine links, and the Display settings disclosure. Page chrome only.

## Use

```js
import { siteHeader } from "/components/site-header/site-header.js";
app.prepend(siteHeader());
```

## Embed

Standalone route: [`/embed/site-header/`](/embed/site-header/). Query parameters:

| Param | Meaning |
|---|---|
| — | none |

Plus the shared embed params `scheme`, `textScale`, `density`, `frameId` (see `docs/THEME_API.md#embeds`).

```html
<div data-nightcal="site-header"></div>
<script src="https://nightcal.justadestination.com/embed.js" async></script>
```

## Events

None.

## Accessibility

- `nav aria-label=Main` with `aria-current=page`; the Display panel is a disclosure that closes on Esc and on outside click.

## Rules

- Two destinations only. New top-level pages go in the footer unless the owner decides otherwise.
- Styling: `site-header.css`, tokens only (checked by `tests/run.mjs`, "token discipline").
