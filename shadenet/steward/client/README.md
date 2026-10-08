# Steward + substrate

Open `index.html` directly — no server, no build step. It loads
`policy.generated.js` (the walkthrough's output, wrapped as a global so `file://`
works).

## What this is

Two things that were specified in `STATUS.md` and had no code behind them:

**The substrate** is the render layer the policy file was always missing. It
measures the live DOM after layout and checks three floors: contrast (per theme,
against `minimumRatio` / `minimumRatioDark`), motion (`motion.locked` plus
`prefers-reduced-motion`), and clutter (`density.clutterCeiling` against visible
competing affordances). If any floor is violated the surface **does not render** —
it is replaced by a refusal panel naming the floor, the element, the measured
ratio and the threshold. Not a warning banner above the article.

**The steward** speaks in the article's own voice during calibration, then steps
into its own register (lighter weight, distinct hue) once it has an answer, and
stays there. It asks one question — tap once for no, keep reading for yes — and
then gets out of the way.

## The invariant this was built around

A recorded preference is never terminal.

The steward records what happened, **says plainly what it recorded**, and leaves
the line in the document as a live control. Tap it to be asked again. Corrections
append to the log and permanently outrank what they correct — they never delete
it. There is a separate **forget this** control for the reader who wants no model
of them at all, which is different from changing an answer.

There is no "never asks again." There is: *does not re-ask unprompted, and can
always be asked.* Those are different things.

## Verified behaviour

Everything below was exercised in a real browser, not reasoned about.

| Behaviour | Result |
|---|---|
| Clean load | `data-substrate: ok`, 0 refusals, surface renders |
| Contrast measurement | 34 element/bg pairs measured off the live DOM |
| Tap → no | Resolves via 400ms window, records `channel: 'tap'` |
| Read-on → yes | Window closes on scroll past the anchor paragraph |
| Escape → no | Keyboard equivalent; tap is not the only way in |
| Confirmation | `Noted: <preference>. Tap this line to change it.` |
| Re-ask via real tap | Works; was **broken** before the `currentAnswered` fix |
| Correction outranks | Entry 1 → `confidence 0.5` + `contradictedBy`, entry 2 appended |
| Correction evidence | Names both the gesture and that a re-ask was needed |
| Revoke | Log emptied, `localStorage` cleared, `window.__stewardLog = []` |
| Re-ask after revoke | Fresh entry at 0.95, not treated as a correction |
| Motion refused | Smile degrades to plain text; acknowledgement survives |
| Morph (motion unlocked) | Animates 0→8px with ease-in, settles to none |
| Smile SVG | `textPath` arc dips 46→59 at midpoint, settles; fill lifts |
| Forced contrast violation | Surface refuses, panel lists the floor |
| Forced clutter violation | Surface refuses, names the ceiling |
| Double resolution | None — log stayed at exactly 2 entries |

## Two real bugs found and fixed during the build

**The re-ask was unanswerable.** `resolve()` guarded on `state.answered`, which
survived a re-ask, so every tap during a correction hit the guard and returned
silently. The preference could be recorded once and never corrected — exactly the
failure the correction path exists to prevent. It passed my first test only
because I called `resolve()` directly with a magic channel. Fixed by guarding on
whether *this* question is answered, and re-tested through real pointer events.

**The substrate refused my own page twice, correctly.** `.hint` rendered at
7.84:1 against a locked 8:1 floor, and the gesture legend counted 4 competing
affordances against a ceiling of 3. Both were real violations, not false
positives. Fixed by solving for compliant colours against *both* dark surfaces
(the hint sits on `--paper-raised` in places, which is why computing against
paper alone gave 8.58 and the browser measured 7.84), and by recognising that a
legend entry is not a competing call to action — nothing in that panel is
tappable.

## The refusal switches

In the dev panel at the bottom: **force a contrast violation** and **exceed the
clutter ceiling**. They exist so the refusal is observable without hand-editing
the policy. A floor you cannot see fail is a floor you have not tested.

## Known limits

- **Motion is locked by the current policy**, so the smile ships as plain text
  and the morph never runs. Both paths are tested — I unlocked motion in memory
  to exercise the SVG — but the default experience is the degraded one. Changing
  that is a policy decision, not a code one.
- **Camera gestures are not wired up.** `gestures.js` renders nod and the
  two-finger raise as a vocabulary key and labels them `not wired up`. Tap
  carries the entire vocabulary alone, which is why it is the one that works
  everywhere. No hand-tracking model is loaded.
- **Reading position is a viewport heuristic** (nearest paragraph to the upper
  third), not eye tracking. It will disagree with a real reader near a boundary.
- **One `id="smile-arc"`** is reused across smiles. Two simultaneous smiles would
  collide; the sequence prevents this, but it is a latent constraint.
- **No coaster.** Nothing here touches AR, camera tracking, or the mosaic. The
  reading surface is the part that could be built and tested without one, so
  that's what this is.

## Files

| File | Role |
|---|---|
| `index.html` | The surface. Article, steward region, gesture panel, inference log |
| `substrate.js` | Measures the DOM, refuses the surface. 3 floors |
| `steward.js` | Sequence, two voices, morph, smile, question window, correction path |
| `gestures.js` | Gesture vocabulary, drawn — including what isn't available |
| `steward.css` | Reading typography. All values from the policy; CSS has fallbacks |
| `policy.generated.js` | `policy.generated.json` as a global. Regenerate from the walkthrough |

Regenerating the policy: `python3 ../walkthrough.py --demo --out ../policy.generated.json`,
then rewrap. Colour values in the CSS are solved, not chosen — if you change the
contrast floors, re-measure rather than assuming they still pass.
