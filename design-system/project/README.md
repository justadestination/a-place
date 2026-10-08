# NightCal Design System

The design system behind NightCal, the self-updating calendar of public nights out in downtown Santa Rosa, and its companion zine, AVR+JIT. Source: `justadestination/a-place` → `tokens/` and `web/`. Every value here is generated from those files.

## Principles

1. **Billboard first.** The answer to "what's on tonight?" is the biggest thing on the screen: the night as a headline, then time and title at 20px bold. Event names are never hidden behind hover.
2. **Boring wins.** System fonts, plain labels ("Nights out", "Everything", "Room"), native controls. One primary action per screen.
3. **Tokens or it doesn't ship.** No raw colour, px or duration in a component. A theme is a set of token overrides. A test fails on a raw value.
4. **Readable for everyone.** Text 13px or larger, targets 44px or larger. Every colour pairing is gated at WCAG 2.2 AA in both themes at build time. Meaning is never carried by colour alone.
5. **Works anywhere.** Every component has a standalone embed route, sized by its content, that talks to its host by postMessage. The same data drives the 2D site and the 3D/AR scene.

## Voice

Short, concrete, local. Say "Tonight", "Tomorrow", "Next: Friday, October 9 (2 shows)". Name the room. Never "Click here", never system jargon. Operational notes ("Instagram asked for a login") belong in the footer under *About this data*, never above the listings.

> Good: "Nothing is listed for tonight yet." · "Listed by the downtown calendar. Also on Facebook."
> Not: "The month hangs open, and the sheet tips forward."

## Colour

Two canonical themes, **Light** (warm paper) and **Dark** (near-black). Both pass AA for every pair in `tokens/pairs.json`.

- `bg`, `surface`, `surface-raised`, `surface-sunken`: four grounds, from the page, to cards, to dialogs, to wells (month cells, the zine map).
- `text` and `text-muted`: the only two text colours. Muted passes 4.5:1 on all four grounds.
- `accent` is **bulb amber** (#FFC14D), kept from the original NightCal. It is a *fill* (the one primary button), never text on light. Use `accent-text` when amber must be text.
- `selected-bg` / `selected-text`: ink in light, amber in dark. Marks the chosen day or segment.
- `focus`: a blue ring, distinct from selection, 3:1 on every ground.
- **Kinds** (`kind-<tone>-bg/fg/mark`): music (green), comedy (coral), show (azure), trivia (violet), food trucks (gold), other (stone). Each tag is a tinted fill with dark or light text (4.5:1), plus a glyph colour (3:1).
- **Zine node types** (`node-<type>`): article, review, letter, editorial, event, venue, entity, and *missing* for links nobody has written yet.

## Shape: glyphs

Kinds and node types each have a shape as well as a colour, so meaning survives without colour: circle (live music, article, event), diamond (comedy, review), square (show, letter), triangle (trivia, editorial), hexagon (food trucks, venue), ring (other, not written yet). In 3D the same shapes become solids: sphere, octahedron, box, tetrahedron, hex prism, torus.

## Type

The system font stack, with no web fonts: nothing to download and nothing to flash. Sizes are rem and scale with the reader's text-size setting (1–2×). The scale runs `xs` 13 · `sm` 14 · `md` 16 · `lg` 20 · `xl` 24 · `2xl` 32 · `3xl` 44 · `display` 36–64 (fluid). Headings are 800 weight with −0.02em tracking. Eyebrows are 14px, 700, uppercase, +0.06em.

## Space, size, motion

- Space `space-1`…`space-8` (4–64px) × `density` (Tight 0.8 · Normal 1 · Roomy 1.25).
- Radius: 6 / 10 / 16 / pill.
- `size-target` 44px is the floor for every control at every density.
- Durations 120 / 200 / 320ms × `motion-scale`, which is 0 under reduced motion. Nothing moves on its own.

## Components

15 components, each a folder in `web/components/` with its JS, CSS, README and a live route at `/embed/<name>/`:

- **Calendar:** EventCard, EventRow, DayAgenda, CalendarWeek, CalendarMonth, FilterBar
- **Zine:** NodeMap (force-directed, pan/zoom, keyboard), ZineReader, ZineCard
- **Content and actions:** KindTag, Button, ShareButton
- **Settings and chrome:** ThemeControls, SiteHeader, SiteFooter

The previews here are static renders captured from the real modules. The interactive versions are the embed routes.

## Theming for agents

A Steward agent restyles the site for one reader with one call. Changes apply live, with no reload and no flash, and are saved for the next visit:

```js
NightCal.theme.apply({ version: 1, scheme: "dark", textScale: 1.5, density: "spacious",
                       schemes: { dark: { "color.accent": "#FF9E5E" } } })
```

Overrides that would break AA contrast are **refused** and reported, and the rest of the spec still applies. The schema is `tokens/theme.schema.json`; the full reference is `docs/THEME_API.md`.

## Embeds

```html
<div data-nightcal="calendar-week" data-theme='{"scheme":"dark"}'></div>
<script src="https://nightcal.justadestination.com/embed.js" async></script>
```

The iframe sizes itself to its content and reports `select` events to the host. The host can send it `theme`, `textScale`, `density` and `scheme` messages.

## Don'ts

- Don't hide event names until hover.
- Don't encode meaning with colour alone.
- Don't tilt or distort the calendar.
- Don't put operational status above listings.
- Don't list rooms with nothing on (that's how closed venues stay off).
- Don't add a second primary button.
- Don't hard-code a value a token already names.
