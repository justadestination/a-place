# Kind tag

What sort of night it is, as text plus a shape. Six kinds: live music, comedy, show, trivia, food trucks, other.

## Use

```js
import { kindTag, kindGlyph } from "/components/kind-tag/kind-tag.js";
row.append(kindTag(event.kind));          // "● Live music"
cell.append(kindGlyph(event.kind));       // shape only, label must be nearby
```

## Embed

Standalone route: [`/embed/kind-tag/`](/embed/kind-tag/). Query parameters:

| Param | Meaning |
|---|---|
| `kind` | see source |

Plus the shared embed params `scheme`, `textScale`, `density`, `frameId` (see `docs/THEME_API.md#embeds`).

```html
<div data-nightcal="kind-tag"></div>
<script src="https://nightcal.justadestination.com/embed.js" async></script>
```

## Events

None.

## Accessibility

- The kind is always given as text; shape and colour are extra cues (1.4.1).
- `kindGlyph` is `aria-hidden`: only use it where the kind is named in text or in the accessible name.

## Rules

- Kinds and tones are defined once in `js/data/calendar.js` (`KINDS`). Add a kind there, plus `kind-<tone>-bg/fg/mark` tokens in both themes and a row in `tokens/pairs.json`.
- Styling: `kind-tag.css`, tokens only (checked by `tests/run.mjs`, "token discipline").
