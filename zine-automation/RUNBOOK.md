# RUNBOOK — one automation run

Follow these steps exactly. If any step fails, log the failure and stop —
never ship a half-built piece.

**Standing Mandate (EDITORIAL_CHARTER.md):**
All drafts must obey the Seven Hard Rules:
1. Ground truth only (no invented facts, drink specials, phantom menus, fake dockets).
2. Opinions clearly framed; all inferences stated out loud ("my inference is...").
3. Mandatory sources cited with working links in a dedicated section.
4. Educational intent: explain and illuminate how systems work.
5. Mandatory editor verification gate before publication.
6. Read-time limit: 5–6 minutes or less (≤ 1,400 words).
7. Backlink chaining: large stories must be decomposed into modular pieces with `[[wikilinks]]`.

## 0. Gate

Roll d100 (use `scripts/state.py gate --chance 40`). If the roll fails:
append a skipped line to `state/run-log.md` and stop. No piece this run.

## 1. Pick

`scripts/state.py pick` → returns a persona + prompt type.
- Never `editors-letter`. Never a persona from `recent_personas`.
- Read the persona file and the prompt file in full before continuing.

## 2. Research

- `browser.search` with the `news` vertical: biggest stories of the last 14 days.
- Verify every factual claim against primary records or legitimate reporting. Zero fabricated facts.
- For `dossier`/`prediction` prompts: do the deeper research the prompt demands
  (8+ sources for dossiers; verifiable baseline metrics for predictions).
- Test all URLs: every cited source must have a working, live link.
- Choose the subject. Check `state.json` → `topics`: if no topic exists for it,
  build one FIRST (step 3). Otherwise link the existing one.

## 3. Topic (only if new subject)

Per `topics/WORKFLOW.md`:
- Create `topics/<slug>/`
- Write `overview.md` from `topics/_template/overview.md` via `prompts/topic-overview.md`
- Write `full-report.md` from `topics/_template/full-report.md` via `prompts/dossier.md`
- Record in state: `scripts/state.py topic <slug>`

## 4. Draft

Write the piece per the prompt file's instructions and `EDITORIAL_CHARTER.md`:
- Ground truth only: unverified claims get cut immediately, not hedged.
- Frame opinions as the persona's perspective; state inferences explicitly out loud.
- Include a dedicated `## Sources` section citing working links.
- Keep read-time to 5–6 minutes or less (word count ceiling: 1,400 words).
- If the subject is expansive, decompose into chained modules using `[[wikilinks]]`.

## 5. Humanize

Run `prompts/humanize-pass.md` against the persona file. All checkboxes.

## 6. Memory

- Append the stance to the persona file's **Stances taken** section
  (newest first): `YYYY-MM-DD — Subject: stance (one line) → drafts/<file>`
- `scripts/state.py stance --persona <id> --subject "..." --stance "..." --draft <file>`
- Predictions: `scripts/state.py predict --persona <id> --claim "..." --check-date YYYY-MM-DD --draft <file>`
- Cartoon briefs: append to nico-varela.md **Cartoon briefs issued**.

## 7. File

Write to `drafts/YYYY-MM-DD-<slug>.md` with the frontmatter from README.md,
`status: draft`. Include `reading_time` (e.g. `4 min read`) and word count in frontmatter.
`drafts/` is the zine's inbox — the editor gate (RUNBOOK-EDITOR.md) picks it up from here.
Nothing publishes straight from the writer run.

## 8. Log

`scripts/state.py log --persona <id> --prompt <type> --draft <file> --notes "..."`
→ updates recent lists, counters, and appends to `state/run-log.md`.
