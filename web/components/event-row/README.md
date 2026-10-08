# Event row

A list item for one event: time, title, room and kind in one 44px+ target. Emits nc-select.

## Use

```js
import { eventRow } from "/components/event-row/event-row.js";
list.append(h("li", {}, eventRow(event)));
list.addEventListener("nc-select", e => open(e.detail.id));
```

## Embed

Standalone route: [`/embed/event-row/`](/embed/event-row/). Query parameters:

| Param | Meaning |
|---|---|
| `id` | event id (defaults to the next night out) |

Plus the shared embed params `scheme`, `textScale`, `density`, `frameId` (see `docs/THEME_API.md#embeds`).

```html
<div data-nightcal="event-row"></div>
<script src="https://nightcal.justadestination.com/embed.js" async></script>
```

## Events

`nc-select` `{ kind: "event", id }`.

## Accessibility

- One `<button>` per event: its accessible name reads time, title, room, kind in visual order.
- Put rows inside `<ol role=list>`.

## Rules

- Time, then title, then room, at billboard sizes (lg). Do not shrink them for density: use the density knob, which only changes spacing.
- Styling: `event-row.css`, tokens only (checked by `tests/run.mjs`, "token discipline").
