# Accessibility audit of the redesign (WCAG 2.2 AA)

**Scope:**
* Every route: 8 pages and 15 embeds.
* At 390×844 (phone) and 1280×860 (desktop), in light and dark: **92 combinations**.
* Plus reflow at 320px, 200% text size, keyboard paths, reduced motion, and a browser without WebGL.

**Method:**
* axe-core 4.10.3 with tags `wcag2a wcag2aa wcag21a wcag21aa wcag22aa best-practice`.
* Custom checks in `web/tests/run.mjs`: text under 12px, targets under 44px, visible focus on every tab stop, keyboard behaviour of the month grid and the node map, theme API contrast enforcement, social metadata, and horizontal scroll.
* The build-time contrast gate in `tokens/build.py`.

**Result:** `npm test` passes with 0 axe violations and 0 custom-check failures. The report is in [`audit/report.json`](audit/report.json).

**Not done:** testing with real assistive technology (NVDA, JAWS, VoiceOver, TalkBack) and with real users. Automated checks cover a minority of WCAG, so treat this as a strong baseline, not a certificate. See "Still to do".

## Fixes applied during this audit

| Found | Criterion | Fix |
|---|---|---|
| Segmented control options were 34px tall | 2.5.8 (and the 44px goal) | Options are now full 44px targets (`css/base.css`) |
| Standalone links (outside a sentence) were 24px tall | 2.5.8 | New `.nc-link` utility; used for every standalone link |
| Week strip in a narrow container gave 41px-wide days | 2.5.8 | Container query switches to 4 columns under 21rem |
| Embeds had no `main` landmark or `h1` | 1.3.1, best practice | `embed.js` wraps each embed in `<main aria-label>` with a visually hidden `h1` |
| Zine card embed skipped a heading level | 1.3.1 | The card renders at h2 when standalone |
| Content overflowed sideways at 320px (system page) and at 200% text on phones | 1.4.10, 1.4.4 | `min-width: 0` on stack and page children; headings wrap anywhere; segmented controls wrap |
| `light` theme: unresolved links and map edges at 2.87:1 on the map background | 1.4.11 | `palette.neutral.400` darkened (#8F897B → #817B6D) to 3.47:1; the build now gates it |
| A theme override could set text to an unreadable colour | 1.4.3 | The theme API refuses overrides that break any pair in `tokens/pairs.json` |
| An embedded frame forgot its initial theme on the first theme message | 1.4.4 | Query-string theme is part of the runtime state, not just the boot script |
| Code samples on `/system/` became scroll regions that keyboard users couldn't reach | 2.1.1 (axe `scrollable-region-focusable`) | Code blocks wrap instead of scrolling |

## Criterion by criterion (AA, including the 2.2 additions)

| Criterion | Status | How |
|---|---|---|
| 1.1.1 Non-text content | Pass | Listing images have alt text naming the event. Glyphs are `aria-hidden` next to a text label. The 3D canvas is `aria-hidden` and the page lists the same items as real controls. |
| 1.3.1 Info and relationships | Pass | Real headings, lists, `dl` for event facts, a `table role=grid` for the month, `fieldset`/`legend` for filters, landmarks on every page and embed |
| 1.3.2 Meaningful sequence | Pass | DOM order = visual order. No CSS reordering. |
| 1.3.4 Orientation | Pass | No orientation lock |
| 1.3.5 Identify input purpose | N/A | No personal-data inputs |
| 1.4.1 Use of colour | Pass | Kind and node type = shape + text. Selected = inverted fill + `aria-pressed`. Today = thick underline or border + "today" in the accessible name. |
| 1.4.3 Contrast (text) | Pass | 50 pairs × 2 themes checked at build ([`tokens/dist/contrast.md`](../tokens/dist/contrast.md)). The lowest text pair is 6.18:1. |
| 1.4.4 Resize text | Pass | All sizes are rem. Text-size knob up to 2×. Tested at 2× at 1280px with no loss. |
| 1.4.5 Images of text | Pass | None (OG images are for social cards, not page content) |
| 1.4.10 Reflow | Pass | No horizontal scroll at 320px on any page |
| 1.4.11 Non-text contrast | Pass | Control borders, focus ring, today marker, glyphs and map edges are at least 3:1, gated at build |
| 1.4.12 Text spacing | Pass | No fixed-height text containers; line clamps only on secondary previews of titles that are shown in full elsewhere |
| 1.4.13 Content on hover or focus | Pass | No hover-only content. Map labels on hover duplicate the accessible name. |
| 2.1.1 Keyboard | Pass | Everything is operable by keyboard. The month grid and node map use roving focus: arrows move, Enter opens, PageUp/PageDown change month, +/− zoom. |
| 2.1.2 No keyboard trap | Pass | Native `<dialog>`, and Esc closes the disclosure menus |
| 2.1.4 Character key shortcuts | Pass | Single keys (+, −, 0) act only while focus is inside the map |
| 2.2.2 Pause, stop, hide | Pass | Nothing moves on its own |
| 2.3.1 Three flashes | Pass | None |
| 2.4.1 Bypass blocks | Pass | "Skip to content" link on every page |
| 2.4.2 Page titled | Pass | Unique titles. The calendar's title tracks the selected night. |
| 2.4.3 Focus order | Pass | Follows reading order. Dialogs move focus to Close and return it on close. |
| 2.4.4 Link purpose | Pass | Links say where they go; external links say they open a new tab |
| 2.4.6 Headings and labels | Pass | One h1 per page; labels on every control |
| 2.4.7 Focus visible | Pass | A 3px focus-token ring on every tab stop (tested on the first 30 stops of `/` and `/zine/`) |
| 2.4.11 Focus not obscured (min) | Pass | No sticky headers over content. The zine reader is sticky only beside the map, never over it. |
| 2.5.1 Pointer gestures | Pass | Pinch-zoom on the map has + and − buttons |
| 2.5.2 Pointer cancellation | Pass | Map selection fires on pointer up, and only without movement |
| 2.5.3 Label in name | Pass | Visible text is part of every accessible name. Day buttons start with the date shown. |
| 2.5.7 Dragging movements | Pass | Panning the map is never required: arrow keys move focus and scroll the view, the zoom buttons work by tap, and the List view shows every node |
| 2.5.8 Target size (min) | Pass, and above it | Every control is at least 44×44 (the project goal; AA asks 24). Inline links in sentences are exempt. |
| 3.1.1 Language of page | Pass | `lang="en"` |
| 3.2.1 / 3.2.2 On focus / on input | Pass | Filters update results in place; nothing navigates on focus |
| 3.2.3 / 3.2.4 Consistent navigation and identification | Pass | Same header and footer everywhere; same components |
| 3.2.6 Consistent help | N/A | No help mechanism yet |
| 3.3.x Input assistance | Pass / N/A | The only free-text input is the JSON box on `/system/`, which reports parse errors in a live region |
| 3.3.7 Redundant entry, 3.3.8 Accessible authentication | N/A | No forms or log-in |
| 4.1.2 Name, role, value | Pass | Native elements first. `aria-pressed` on selectable days and nodes, `aria-current` for today and the current page, `aria-expanded` on disclosures. |
| 4.1.3 Status messages | Pass | `role=status` for "Link copied", the 3D loading state and theme API results |

## Beyond AA (deliberate)

* 44px targets everywhere (AA is 24px).
* A 12px text floor; the smallest token is 13px.
* `prefers-reduced-motion` plus an in-page motion control. Under reduced motion, every duration token becomes 0ms.
* A text size and spacing control in the header, so readers don't need browser zoom.
* The node map always has a List view.

## Still to do

1. **Screen reader passes**: NVDA + Firefox, JAWS + Chrome, VoiceOver on iOS and macOS, TalkBack. These are especially needed for the month grid (`role=grid` with buttons) and the node map (roving `role=button` inside an SVG `role=group`).
2. **Usability with disabled readers.** The node map is a novel pattern; the List view is the safe path until it is tested.
3. **Per-event alt text.** The backend gives image URLs, not descriptions. The alt currently says "Listing image for <title>". Better alt needs a description field in the data (backend team).
4. **No-JS listings.** These need server rendering (backend team). The pages currently say JavaScript is needed.
5. **The 3D/AR scene.** The DOM list is the accessible equivalent. Spatial-UI accessibility (gaze dwell, captions in AR) is not addressed in this prototype.
