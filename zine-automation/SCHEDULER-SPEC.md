# Scheduler spec — zine-owned automations

These two jobs belong to **Umwelt Horizons**, not to Dexa. They are platform
automations under master-todo **6.9** (done-when: each automation has an owner,
a schedule, and a failure alert).

## Job 1 — `umwelt-horizons/writer-run`

- **Owner:** the zine (Operators oversee)
- **Schedule:** every 8 hours, with a ~40% probabilistic gate per run
  (≈1 piece/day at genuinely random-feeling times)
- **Does:** RUNBOOK.md — gate → pick persona+prompt → research recent news →
  build topic dossier if the subject is new → draft → humanize pass →
  append stance to persona memory + state → file to `drafts/` (the zine's inbox)
- **Inputs:** `personas/`, `prompts/`, `state/state.json`
- **Outputs:** `drafts/*.md` (status: draft), `topics/<slug>/`
- **Never:** picks `editors-letter` (the operator's slot); embeds any cipher (on hold)
- **Failure alert:** log to `state/run-log.md`; report to Operators if a run
  fails in a way that blocks future runs (not one-off gate skips)

## Job 2 — `umwelt-horizons/editor-run`

- **Owner:** the zine (Operators oversee; editor acts as Dev Malik)
- **Schedule:** every 8 hours, offset from the writer run
- **Does:** RUNBOOK-EDITOR.md — take the queue oldest-first → copy-edit per
  `prompts/editor-pass.md` → gate decision
- **Gate clears →** `scripts/state.py publish` → `published/` (status: published)
- **Gate triggers →** `scripts/state.py escalate` → `needs-operator/` + reason,
  always reported to Operators. Uncertainty itself is a trigger.
- **Inputs:** `drafts/`, draft topics
- **Outputs:** `published/*.md` (the outbox the zine pipeline ingests),
  `needs-operator/*.md`
- **Failure alert:** same as Job 1; escalations are always surfaced, never silent

## State

`state/state.json` is the shared state file (stdlib-only `scripts/state.py`
manipulates it — portable to any host). Persona `Stances taken` sections are
the human-readable half of the memory; both are append-only.

## Interim runner (until the platform implements this)

Both jobs currently execute on **Dexa's scheduler** as an interim measure:

- `zine-automation-run` (writer) and `zine-automation-editor` (editor)

**Migration:** implement as native platform jobs (e.g. systemd timers on the
the host host running the runbooks against a repo checkout), then **disable
Dexa's crons** — never double-run. The runbooks, prompts, personas, and
`state.py` move over unchanged.
