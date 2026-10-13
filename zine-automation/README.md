# Zine automation system

Randomized, persona-driven article generator for Umwelt Horizons.
Built 2026-10-09 per the operator. He writes the intro/editorial himself;
everything else runs on this system.

**Ownership:** these are the zine's jobs, not Dexa's. See `SCHEDULER-SPEC.md`
for the platform spec (master-todo 6.9). Hermes cron on this machine runs
them: `umwelt-horizons/writer-run` and `umwelt-horizons/editor-run`. Dexa's
old cron names are not installed. Do not add a second runner.

## How it works

Two stages, fully automated. The editor is the gate; operators can step in
on anything, anytime.

**Stage 1 — writer** (Hermes cron `umwelt-horizons/writer-run`, `0 */8 * * *`, ~40% gate):
1. Picks a persona + prompt type at random (recency-weighted, never repeats
   a persona used in the last 5 runs; never picks `editors-letter`)
2. Researches recent news (news vertical) for a subject
3. If the subject has no topic yet → builds one first
   (`topics/<slug>/`: neutral `overview.md` + full `full-report.md`)
4. Drafts the piece per the prompt's instructions
5. Runs the humanize pass against the persona file
6. Appends the stance to the persona's **Stances taken** memory + state.json
7. Files the draft to `drafts/` (the zine's inbox), `status: draft`

**Stage 2 — editor** (Hermes cron `umwelt-horizons/editor-run`, `0 4,12,20 * * *`):
1. Takes the queue oldest-first: `drafts/*.md` + draft topics
2. Copy-edits each piece as Dev Malik (`prompts/editor-pass.md`)
3. Gate clears → `scripts/state.py publish` → `published/`, `status: published`
4. Gate triggers → `scripts/state.py escalate` → `needs-operator/` + reason,
   always reported to the operator. Uncertainty itself is a trigger — the fallback
   is the operators, that's what they're for.

`needs-operator/` is the operator inbox. the operator steps in whenever he wants,
on anything, at any stage.

> Platform note: the NightCal Boxes (real zine/operator inboxes in the app)
> are platform scope, not this automation's. When they land, `drafts/` and
> `needs-operator/` map onto them.

## Layout

```
zine-automation/
  README.md            — this file
  RUNBOOK.md           — step-by-step instructions the cron run follows
  CIPHER.md            — HELD: the operator is designing the cipher. Do not embed yet.
  personas/            — 13 roster files, each with append-only stance memory
  prompts/             — 7 prompt files (hot-take, dossier, prediction,
                         topic-overview, cartoon-brief, humanize-pass,
                         editors-letter [OPERATOR-OWNED, never auto-picked])
  topics/              — per-subject dossiers (overview + full report)
    _template/         — blank templates
    WORKFLOW.md        — topic creation rules
  drafts/              — the zine's inbox: writer output, status: draft,
                         awaiting the editor gate
  published/           — cleared by the editor, status: published.
                         THIS is the publish outbox the zine pipeline ingests.
  needs-operator/      — the operator inbox: escalations with reasons.
                         the operator steps in here whenever he wants.
  state/
    state.json         — machine state (see STATE SCHEMA below)
    run-log.md         — human-readable run history
  scripts/
    state.py           — state helpers (pick, record, log)
```

## Draft frontmatter

```yaml
---
title: "..."
author: <persona name> (<screenname>)
persona: <personas/<file>>
type: stance | dossier-piece | prediction | cartoon-brief
prompt: <prompts/<file>>
date: YYYY-MM-DD
topic: <slug>          # if tied to a news subject
stance: <one line>     # if the piece takes one
status: draft
---
```

Body uses `[[topic-slug]]` wikilinks for graph edges (zine pipeline convention).

## State schema (state/state.json)

```json
{
  "personas": ["mags-pilecki", "juno-voss", "mara-okwonko", "dev-malik",
               "nico-varela", "priya-raman", "silas-brandt", "bea-luna",
               "dante-morales", "esme-navarro", "felix-brauer",
               "julian-croft", "camilla-thorne"],
  "recent_personas": ["<last 5 used>"],
  "recent_prompts": ["<last 5 used>"],
  "topics": {"<slug>": {"created": "YYYY-MM-DD", "overview": true, "report": true}},
  "stances": [{"date": "...", "persona": "...", "subject": "...",
               "stance": "...", "draft": "drafts/<file>"}],
  "predictions": [{"date": "...", "persona": "...", "claim": "...",
                   "check_date": "YYYY-MM-DD", "draft": "...", "result": null}],
  "runs": <int>,
  "pieces": <int>,
  "published": <int>
}
```

## Rules (changeable — the operator: "we can change the rules when we need to")

- Stance memory is append-only. A persona stays consistent with past stances
  unless they publicly change their mind *in a piece* (Mara does this
  theatrically; others need a reason on the page).
- Topics are neutral. Opinion pieces link to them; they never take sides.
- Predictions get scored when their check date arrives.
- The cipher is ON HOLD. Nothing gets embedded until the operator finishes the scheme.
- the operator's intro/editorial slot is his. The automation never touches it.
- Keyword research (`Keyword_Research_1min_AI_2026-10-09…xlsx`, in
  `workspace/user/files/`) is thin but usable: "controversial news topics"
  has real volume — the hot-take prompt may weight toward it for SEO.
