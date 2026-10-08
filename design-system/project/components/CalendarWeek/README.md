# Calendar week

A seven-day strip. Counts on narrow screens, counts plus event titles on wide ones. Emits nc-select and nc-shift.

## Use

```js
import { calendarWeek } from "/components/calendar-week/calendar-week.js";
import { weekScene } from "/js/data/scene.js";
slot.append(calendarWeek(weekScene(model, { date, scope, venueId })));
```

## Embed

Standalone route: [`/embed/calendar-week/`](/embed/calendar-week/). Query parameters:

| Param | Meaning |
|---|---|
| `date` | any day in the week (defaults to today) |
| `scope` | nights | all |
| `venue` | venue id |

Plus the shared embed params `scheme`, `textScale`, `density`, `frameId` (see `docs/THEME_API.md#embeds`).

```html
<div data-nightcal="calendar-week"></div>
<script src="https://nightcal.justadestination.com/embed.js" async></script>
```

## Events

`nc-select` `{ kind: "day", date }`; `nc-shift` `{ unit: "week", delta }`.

## Accessibility

- Seven `<button aria-pressed>` with full spoken names ("Friday, October 9, 2 shows"); `aria-current=date` on today.
- Visible titles inside are `aria-hidden` because the agenda lists them for real.

## Rules

- Counts under 52rem container width, first three titles above it. Under 21rem it becomes 4 columns so targets stay at least 44px.
- The same `weekScene` feeds the 3D week; keep them in sync by changing the scene, not the component.
- Styling: `calendar-week.css`, tokens only (checked by `tests/run.mjs`, "token discipline").
