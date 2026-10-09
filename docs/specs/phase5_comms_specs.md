# Phase 5 (Batch F) — build specs (Dexa, 2026-10-09)

Specs for Hermes to implement against. Lexicon: Spots (events), Spaces
(venues), Expressions (articles), Thoughts (mail), Boxes (inboxes),
Listed (entities). Test build: Santa Rosa only, the host, SQLite.

## 5.1 Matrix — embedded chat node (DECIDED 2026-10-09, the operator)

Self-hosted Synapse (the operator's infra — server URL via config), embedded as a
chat node inside NightCal. No Element link-out.

- **Surface:** a chat node in the NightCal UI (same node pattern as the
  portal): rooms list → room view → composer. Independently frameable
  (`/embed/chat`), Steward-customizable like everything else.
- **Auto-login:** zero user steps. The Steward authenticates to Synapse
  transparently using the Steward credential — the user never sees a Matrix
  login. Mechanism: Synapse JWT SSO (or shared-secret login) with the
  Steward minting short-lived tokens.
- **Anonymized identity:** the Matrix user ID is a pseudonym
  (`@anon-<random>:<server>`), never the platform username. The
  pseudonym↔user mapping lives server-side and is never exposed to other
  chatters.
- **Steward as helper:** the Steward is present in rooms — test-build scope:
  answers questions about Spots ("what's on tonight?"), surfaces attention
  items (ties to 2.7). Acts only with user approval where actions are
  concerned.
- **Rooms:** one per Space + one Domain-general room. Federation off or
  allowlist-only for the test build.
- **Moderation:** Operators moderate (kick/ban/redact); basic spam controls.
- **Privacy:** room content persists — it is NOT part of the self-destructing
  Thoughts model. Say so in the UI and the privacy policy (8.1).

**Done when:** user opens the chat node and is chatting within ~2 seconds
with no login step; other users see only the pseudonym; the Steward helper
answers "what's on tonight?" from the calendar; an Operator can moderate.
**Tests:** `[e2e]` open node → auto-logged-in → send → received by a second
test user under the pseudonym; `[e2e]` no Matrix login screen ever appears;
`[abuse]` second user cannot resolve a pseudonym to a platform username;
`[manual]` mobile walkthrough.

**Needs from the operator:** Synapse server URL + the SSO/shared-secret wiring on
his infra.

## 5.2 Image support

- **Upload:** webp, jpeg, png, gif. 10 MB max per file; server resizes to max
  2048px on the long edge and generates responsive variants
  (480/960/1600w) + a blur placeholder. Validate by magic bytes, not
  extension. **Strip EXIF on ingest** (GPS is a privacy leak).
- **Storage (test build):** local disk on the host under `/media`, served by
  the web tier, included in the backup set (6.4). No new infra.
- **Alt text is required** — the publish API rejects `alt == ""` and the UI
  blocks the publish button until it's filled. Decorative images get
  `alt=""` explicitly + `role="presentation"` (a conscious choice, not a
  missing field).
- **Rendering:** `<figure>` + `<figcaption>` where a caption exists,
  `loading="lazy"`, `srcset`/`sizes`, never upscale beyond native.
- **Abuse tests:** oversized file rejected; `.exe` renamed to `.png` rejected
  (magic bytes); EXIF GPS stripped — assert no GPS tags survive.

## 5.3 Comics — format spec

A comic is an Expression with `format: comic`:

```json
{
  "format": "comic",
  "title": "...",
  "panels": [
    { "image": "<media id>", "alt": "required",
      "caption": "optional", "dialogue": "optional" }
  ]
}
```

- Panels are an ordered array; the reader shows one panel at a time on
  mobile (swipe / tap / arrow keys) and panel-flow on desktop.
- Keyboard: ←/→ navigate, Home/End jump. Focus management on panel change
  (announce via `aria-live`).
- Panel images go through the 5.2 pipeline (alt required per panel).
- Reader UI is a Steward-customizable view like everything else: data +
  structure + presentation hooks, no bespoke one-off styling.
- Done-when: a 6-panel sample comic reads cleanly on a phone and a desktop.

## 5.4 Notifications

Types: (a) earmarked-Spot reminders (default 2h before, user-settable);
(b) cancellation notices for earmarked Spots (existing promise);
(c) optional daily digest of today's Spots.

- **Channel (test build):** in-Box Thoughts first — the platform already has
  Boxes, so a "NightCal reminders" sender is nearly free. Email as fallback
  only if the user sets one. Push (service worker) is deferred — not the
  core loop.
- **Prefs:** per-type on/off in settings (4.6); one master kill switch.
  Default: reminders on, digest off.
- **Cancellation path:** Spot cancelled → everyone who earmarked it gets a
  Thought within 5 minutes. This is a promise — test it like one.
- Tests: `[int]` trigger each type; `[e2e]` prefs disable each type;
  `[e2e]` cancelled Spot → notice arrives.

## 5.5 iCal feed

- Routes: `/ical` (all Spots) and `/ical/space/<space-id>` (per Space).
- RFC 5545. Per event: `UID` = `<spot-id>@shady.example.org`
  (stable across regenerations), `DTSTAMP`/`SEQUENCE` bump on change,
  `DTSTART`/`DTEND` with `TZID=America/Los_Angeles`, `SUMMARY`, `DESCRIPTION`
  (first ~500 chars + link), `LOCATION` (Space name + address), `URL`
  (canonical Spot URL).
- Cancelled Spots: emit with `STATUS:CANCELLED` (keeps subscribers' clients
  honest) rather than silently vanishing.
- `X-WR-CALNAME`: "NightCal — Santa Rosa".
- Regenerate from the DB on each request (corpus is small); add HTTP caching
  (`ETag`/`Last-Modified`) when it gets slow.
- Tests: `[int]` feed validates against an iCalendar validator;
  `[manual]` import into Google Calendar and Apple Calendar, then change a
  Spot and confirm the update propagates.

## 5.6 Search

- **Engine:** SQLite FTS5 — no new infra, corpus is small.
- **Scope:** Spots (title + description), Spaces (name + address), Listed
  (name + bio), Expressions (title + body).
- **Ranking:** title matches outrank body matches; upcoming Spots outrank
  past ones; exact-phrase matches outrank token soup. Keep it explainable —
  no ML ranking for the test build.
- **UI:** one search box, results grouped by type with type labels, keyboard
  navigable, `<500ms` on the full corpus (measure it, don't assert it).
- Tests: `[int]` fixture queries with known expected top hits (e.g. "jazz"
  → the jazz Spot first); empty query and gibberish degrade gracefully.

## Cross-cutting

- All new UI copy uses the lexicon. All new views get `/embed` routes and
  meet the 12px / 44px / zero-axe-violations bar from the design system.
- Nothing here sends mail or notifications without the user's opt-in
  (prefs in 4.6, except cancellation notices for earmarked Spots — that's
  the promise).
