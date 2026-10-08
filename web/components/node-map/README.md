# Zine node map

The zine as a force-directed graph: notes, events, venues and unresolved links. Pan, zoom, keyboard navigation, select to read.

## Use

```js
import { nodeMap } from "/components/node-map/node-map.js";
import { graphScene } from "/js/data/graph.js";
const map = nodeMap(graphScene(zine, { dims: 2 }), { selectedId });
map.addEventListener("nc-select", e => read(e.detail.id));
map.select(id); // highlight from outside
```

## Embed

Standalone route: [`/embed/node-map/`](/embed/node-map/). Query parameters:

| Param | Meaning |
|---|---|
| `node` | node id to highlight |

Plus the shared embed params `scheme`, `textScale`, `density`, `frameId` (see `docs/THEME_API.md#embeds`).

```html
<div data-nightcal="node-map"></div>
<script src="https://nightcal.justadestination.com/embed.js" async></script>
```

## Events

`nc-select` `{ kind: "node", id }`.

## Accessibility

- One tab stop. Arrow keys move to the nearest node in that direction, Enter/Space opens, +/− zoom, 0 fits.
- Each node is `role=button` with "Type: Title. N links." as its name; `aria-pressed` marks the selection.
- Pinch and drag are optional: the zoom buttons, keyboard and a List view (on the zine page) cover everything (2.5.1, 2.5.7).

## Rules

- Marks are drawn in screen pixels and counter-scaled on zoom, so dots and labels stay readable at any zoom and on any screen; zooming spreads them out.
- Notes are always labelled; other nodes are labelled when zoomed in, focused, hovered, or next to the selection.
- Styling: `node-map.css`, tokens only (checked by `tests/run.mjs`, "token discipline").
