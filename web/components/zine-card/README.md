# Zine card

One zine node as a card: type, title link, byline, summary. Works without script.

## Use

```js
import { zineCard } from "/components/zine-card/zine-card.js";
list.append(h("li", {}, zineCard(node, { level: 3 })));
```

## Embed

Standalone route: [`/embed/zine-card/`](/embed/zine-card/). Query parameters:

| Param | Meaning |
|---|---|
| `node` | node id (defaults to the first note) |
| `type` | article | review | letter | editorial | event | venue | missing |

Plus the shared embed params `scheme`, `textScale`, `density`, `frameId` (see `docs/THEME_API.md#embeds`).

```html
<div data-nightcal="zine-card"></div>
<script src="https://nightcal.justadestination.com/embed.js" async></script>
```

## Events

`nc-select` `{ kind: "node", id }` (plain click); modified clicks follow the real link.

## Accessibility

- The title is a real link to `/zine/?node=<id>`, stretched over the card, so it works without script. The focus ring is drawn on the card.

## Rules

- Node-type colours come from `color-node-<type>` tokens; the type is always written out.
- Styling: `zine-card.css`, tokens only (checked by `tests/run.mjs`, "token discipline").
