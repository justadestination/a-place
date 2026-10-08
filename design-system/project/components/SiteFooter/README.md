# Site footer

About this data (status, closures), the required OpenStreetMap attribution, and secondary links.

## Use

```js
import { siteFooter } from "/components/site-footer/site-footer.js";
app.append(siteFooter({ notes: model.notes, source: model.source }));
```

## Embed

Standalone route: [`/embed/site-footer/`](/embed/site-footer/). Query parameters:

| Param | Meaning |
|---|---|
| — | none |

Plus the shared embed params `scheme`, `textScale`, `density`, `frameId` (see `docs/THEME_API.md#embeds`).

```html
<div data-nightcal="site-footer"></div>
<script src="https://nightcal.justadestination.com/embed.js" async></script>
```

## Events

None.

## Accessibility

- Data notes sit behind a native `details` disclosure.

## Rules

- The OpenStreetMap attribution stays visible (licence requirement). Operational status text lives here, never above the calendar.
- Styling: `site-footer.css`, tokens only (checked by `tests/run.mjs`, "token discipline").
