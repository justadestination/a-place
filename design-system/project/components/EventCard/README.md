# Event card

One event in full: kind, title, when, where, lineup, sources, and the single primary action (the listing).

## Use

```js
import { eventCard } from "/components/event-card/event-card.js";
dialog.append(eventCard(event, { venue, today: model.today, level: 2 }));
```

## Embed

Standalone route: [`/embed/event-card/`](/embed/event-card/). Query parameters:

| Param | Meaning |
|---|---|
| `id` | event id (defaults to the next night out) |
| `image` | 0 to hide the listing image |

Plus the shared embed params `scheme`, `textScale`, `density`, `frameId` (see `docs/THEME_API.md#embeds`).

```html
<div data-nightcal="event-card"></div>
<script src="https://nightcal.justadestination.com/embed.js" async></script>
```

## Events

None of its own (the share button handles itself).

## Accessibility

- An `article` labelled by its title; facts in a `dl`.
- External links announce that they open a new tab.
- The listing image has alt text and fixed dimensions (no layout shift).

## Rules

- Its one primary action is the source listing. Do not add a second primary.
- Becomes two columns at container width 44rem or more (container query), so it works in dialogs, embeds and pages.
- Styling: `event-card.css`, tokens only (checked by `tests/run.mjs`, "token discipline").
