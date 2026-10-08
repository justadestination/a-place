# Calendar month

Month grid with date-picker keyboard support (arrows, Home/End, PageUp/PageDown). Counts on narrow screens, titles on wide.

## Use

```js
const { calendarMonth } = await import("/components/calendar-month/calendar-month.js"); // lazy: below the fold
slot.append(calendarMonth(monthScene(model, { month, date })));
```

## Embed

Standalone route: [`/embed/calendar-month/`](/embed/calendar-month/). Query parameters:

| Param | Meaning |
|---|---|
| `month` | YYYY-MM (defaults to this month) |
| `date` | selected day |
| `scope` | nights | all |
| `venue` | venue id |

Plus the shared embed params `scheme`, `textScale`, `density`, `frameId` (see `docs/THEME_API.md#embeds`).

```html
<div data-nightcal="calendar-month"></div>
<script src="https://nightcal.justadestination.com/embed.js" async></script>
```

## Events

`nc-select` `{ kind: "day", date }`; `nc-shift` `{ unit: "month", delta, focusDate? }`.

## Accessibility

- `table role=grid` with one tab stop (roving tabindex). Arrows move by day/week, Home/End go to the week's ends, PageUp/PageDown change month, and moving past the edge changes month.
- Each day button has a full spoken name; the visual count and titles are `aria-hidden`.

## Rules

- Load it with `import()` when it nears the viewport; it is the heaviest calendar component.
- Styling: `calendar-month.css`, tokens only (checked by `tests/run.mjs`, "token discipline").
