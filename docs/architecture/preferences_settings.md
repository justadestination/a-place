# Preference and settings tabs

**Status:** Task 4.6
**Specification:** `nightcal-master-todo.md` Section 4.6

## What this is

One settings surface for notification preferences, muted venues, theme, density, text size, motion, and steward settings. A change applies on the page immediately and is stored for the next session and for any other signed-in device.

## Where it lives

- Component: `web/components/preference-tabs/`
- Embed: `/embed/preference-tabs/?session=<token>`
- API: `GET` and `POST /api/auth/preferences`
- Store: `AuthStore.set_user_preferences` in `shadenet/auth.py`

`POST` accepts `{"preferences": {...}}` or a bare object. Auth is `Authorization: Bearer`, `X-Session-Token`, or the `session` query on GET.

## Persistence

The stored document is a deep merge. A partial update replaces the keys it sends and leaves the rest. Nested objects such as `notifications` merge key by key. Arrays such as `muted_venues` replace as a whole.

A second session for the same user reads the same document, so a change on one device shows up on another.

Without a session the component keeps a copy in `localStorage` under `nightcal.prefs.v1:`.

## Live display

Theme, density, text size, and motion call the public theme API (`setScheme`, `setDensity`, `setTextScale`, `setMotion`) as soon as the control changes. The same values are written to the preferences API.

## Tokens

The component stylesheet uses design tokens only. Controls use `min-height: var(--nc-size-target)`.
