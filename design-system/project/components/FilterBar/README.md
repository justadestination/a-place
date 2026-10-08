# Filter bar

Nights out vs everything, and one room. Native radios and select, so keyboard and screen readers work without extra code. Emits nc-filter.

## Use

```js
import { filterBar } from "/components/filter-bar/filter-bar.js";
const bar = filterBar({ scope, venueId, rooms: roomsWithEvents(model, { scope: "all" }) });
bar.addEventListener("nc-filter", e => update(e.detail));
```

## Embed

Standalone route: [`/embed/filter-bar/`](/embed/filter-bar/). Query parameters:

| Param | Meaning |
|---|---|
| `scope` | nights | all |
| `venue` | venue id |

Plus the shared embed params `scheme`, `textScale`, `density`, `frameId` (see `docs/THEME_API.md#embeds`).

```html
<div data-nightcal="filter-bar"></div>
<script src="https://nightcal.justadestination.com/embed.js" async></script>
```

## Events

`nc-filter` `{ scope, venueId }`.

## Accessibility

- Native radios in a `fieldset`/`legend`, and a native `select` with a `label`, so no ARIA is needed.

## Rules

- **Only pass rooms that have listings** (`roomsWithEvents`). That is how closed venues stay off the page without a backend change.
- Styling: `filter-bar.css`, tokens only (checked by `tests/run.mjs`, "token discipline").
