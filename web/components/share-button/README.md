# Share button

Native share sheet when available; otherwise copy link, X, Bluesky, Facebook and email intents.

## Use

```js
import { shareButton } from "/components/share-button/share-button.js";
bar.append(shareButton({ title, text, url }));
```

## Embed

Standalone route: [`/embed/share-button/`](/embed/share-button/). Query parameters:

| Param | Meaning |
|---|---|
| `url` | URL to share (defaults to the page) |
| `title` | share title |
| `text` | share text |

Plus the shared embed params `scheme`, `textScale`, `density`, `frameId` (see `docs/THEME_API.md#embeds`).

```html
<div data-nightcal="share-button"></div>
<script src="https://nightcal.justadestination.com/embed.js" async></script>
```

## Events

None.

## Accessibility

- A disclosure (`aria-expanded`, `aria-controls`); Esc closes and returns focus.
- "Link copied" is announced through `role=status`.

## Rules

- Uses `navigator.share` where it exists (most phones); otherwise copy link, X, Bluesky, Facebook and email intents. No third-party scripts or tracking pixels.
- Styling: `share-button.css`, tokens only (checked by `tests/run.mjs`, "token discipline").
