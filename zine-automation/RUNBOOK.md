# RUNBOOK — one automation run

Follow these steps exactly. If any step fails, log the failure and stop —
never ship a half-built piece.

## 0. Gate

Roll d100 (use `scripts/state.py gate --chance 40`). If the roll fails:
append a skipped line to `state/run-log.md` and stop. No piece this run.

## 1. Pick

`scripts/state.py pick` → returns a persona + prompt type.
- Never `editors-letter`. Never a persona from `recent_personas`.
- Read the persona file and the prompt file in full before continuing.

## 2. Research

- `browser.search` with the `news` vertical: biggest stories of the last 14 days.
- For `dossier`/`prediction` prompts: do the deeper research the prompt demands
  (8+ sources for dossiers; verification for predictions).
- Choose the subject. Check `state.json` → `topics`: if no topic exists for it,
  build one FIRST (step 3). Otherwise link the existing one.

## 3. Topic (only if new subject)

Per `topics/WORKFLOW.md`:
- Create `topics/<slug>/`
- Write `overview.md` from `topics/_template/overview.md` via `prompts/topic-overview.md`
- Write `full-report.md` from `topics/_template/full-report.md` via `prompts/dossier.md`
- Record in state: `scripts/state.py topic <slug>`

## 4. Draft

Write the piece per the prompt file's instructions. Verify every factual claim
during research — unverified claims get cut, not hedged.

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
`status: draft`. `drafts/` is the zine's inbox — the editor gate
(RUNBOOK-EDITOR.md) picks it up from here. Nothing publishes straight from
the writer run.

## 8. Log

`scripts/state.py log --persona <id> --prompt <type> --draft <file> --notes "..."`
→ updates recent lists, counters, and appends to `state/run-log.md`.
