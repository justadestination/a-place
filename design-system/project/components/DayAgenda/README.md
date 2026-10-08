# Day agenda

One night as a billboard: the date as a headline and every event as a large row. Has an empty state that jumps to the next night with events.

## Use

```js
import { dayAgenda } from "/components/day-agenda/day-agenda.js";
import { dayScene } from "/js/data/scene.js";
main.append(dayAgenda(dayScene(model, { date }), { today: model.today, level: 1 }));
```

## Embed

Standalone route: [`/embed/day-agenda/`](/embed/day-agenda/). Query parameters:

| Param | Meaning |
|---|---|
| `date` | YYYY-MM-DD (defaults to today) |
| `scope` | nights | all |
| `venue` | venue id |

Plus the shared embed params `scheme`, `textScale`, `density`, `frameId` (see `docs/THEME_API.md#embeds`).

```html
<div data-nightcal="day-agenda"></div>
<script src="https://nightcal.justadestination.com/embed.js" async></script>
```

## Events

`nc-select` `{ kind: "event", id }` from rows; `{ kind: "day", date }` from the empty-state jump.

## Accessibility

- A `section` labelled by its heading; set `level` so the page outline stays correct (h1 on the calendar, h2 elsewhere).
- Wrap it in `aria-live=polite` if it re-renders on filter changes (the calendar page does).

## Rules

- "Tonight" and "Tomorrow" are the headline when they apply; the full date sits above as an eyebrow.
- An empty night never dead-ends: pass `next` to offer a jump, or render the next night below (the calendar does both).
- Styling: `day-agenda.css`, tokens only (checked by `tests/run.mjs`, "token discipline").
