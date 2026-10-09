# Chat Component (Task 5.1)

Self-contained embedded Matrix chat node for NightCal patrons, venues, and stewards.

## Features
- **Zero-step transparent login**: Mints anonymous pseudonyms (`@anon-<hash>:shady.example.org`) mapped server-side to the user session. No Matrix login screen appears.
- **Room topology**: Town-wide Domain-general (`#downtown-general`) and individual Space rooms per venue.
- **Steward in-room helper**: The `@steward` bot answers queries such as *"what's on tonight?"* using the live calendar data.
- **Privacy notice**: Informs patrons that room messages are public and persist, unlike ephemeral in-box Thoughts.
- **Touch target discipline**: All interactive room buttons, inputs, and send buttons meet WCAG 2.2 AA target size (≥ 44px).
- **Design tokens**: 100% token usage (0 raw hex colors, 0 raw px units).
- **External Matrix bridge**: Links out to `chat.example.org` for users with external Element clients.

## Embed usage
```html
<iframe src="/embed/chat/?room=!general:shady.example.org" width="100%" height="600" title="NightCal Chat"></iframe>
```
