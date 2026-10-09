# Preference & Settings Tabs Component (`preference-tabs`)

Implements **Task 4.6: Preference / settings tabs**.

## Features

- **One persistent settings hub** with four tabs: Notifications, Muted Venues,
  Theme & Display, and Steward.
- **Live apply**: theme, density, text scale and motion update the document
  immediately through the public theme API (`window.NightCal.theme`). No reload.
- **Persist across sessions**: settings are pushed to the preferences API
  (`POST /api/auth/preferences`) and also written to `localStorage` under
  `nightcal.prefs.v1:<username>` as a safe boot fallback.
- **Deep-merge semantics**: the server replaces the stored JSON with the keys
  the caller sent, but keeps unmentioned keys, so a partial tab save never
  wipes another section.
- **Strict design tokens**: zero raw hex colors and zero raw px in CSS.
  Interactive touch targets use `min-height: var(--nc-size-target)` (>= 44px).
- **WCAG 2.2 AA**: keyboard focus on every control, `aria-selected` on tabs,
  `aria-live` status announcements, and `required` labels.

## API

| Endpoint | Method | Body | Notes |
|---|---|---|---|
| `/api/auth/preferences` | GET | — | Returns `{"preferences": {...}}`. Session required. |
| `/api/auth/preferences` | POST | `{"preferences": {...}}` or bare `{...}` | Replaces stored JSON with a deep merge. |

Client requests authenticate with `Authorization: Bearer <token>` or
`X-Session-Token`. `AuthManager`/`AuthStore` reject invalid or revoked sessions.
`set_user_preferences` replaces the stored JSON (deep merge); empty initial
preferences are `{}`.

## Embed

Standalone route: `/embed/preference-tabs/`. Query parameters
(`scheme`, `textScale`, `density`) are honoured by the theme boot script for the
first paint inside the iframe.

```html
<div data-nightcal="preference-tabs"></div>
<script src="https://nightcal.example.org/embed.js" async></script>
```

JS:

```js
import { preferenceTabsView } from "/components/preference-tabs/preference-tabs.js";
const root = document.getElementById("app");
root.append(preferenceTabsView({ apiBase: "https://nightcal.example.org", sessionToken: "sess_xxx" }));
```

## Events

- Listens for `nightcal:themechange` on `document`; the tab UI re-syncs the
  radio/`theme` groups without overwriting the user's current radio choice.

## Design tokens

All values ship from `tokens.css` and `nightcal.css`. The component CSS contains
no `#[0-9a-f]` literal and no `px` unit. Verified by `tests/run.mjs` (token
discipline) and the E2E axe run (0 violations).
