# Zine reader

Reads one zine node (note, event, venue or unresolved link) and lists what it links to.

## Use

```js
import { zineReader } from "/components/zine-reader/zine-reader.js";
panel.replaceChildren(zineReader(node, { graph, calendar }));
```

## Embed

Standalone route: [`/embed/zine-reader/`](/embed/zine-reader/). Query parameters:

| Param | Meaning |
|---|---|
| `node` | node id (defaults to the first note) |

Plus the shared embed params `scheme`, `textScale`, `density`, `frameId` (see `docs/THEME_API.md#embeds`).

```html
<div data-nightcal="zine-reader"></div>
<script src="https://nightcal.justadestination.com/embed.js" async></script>
```

## Events

`nc-select` `{ kind: "node", id }` from in-text [[links]], linked cards and venue event rows.

## Accessibility

- The title is focusable (`tabindex=-1`); move focus to it when a new node opens.
- Note bodies are rendered to HTML at build time with everything escaped (`tools/build_zine.py`). Never inject note text at runtime.

## Rules

- Events show the full event card; venues list what's on there; unresolved links say that nothing has been written yet.
- Styling: `zine-reader.css`, tokens only (checked by `tests/run.mjs`, "token discipline").
