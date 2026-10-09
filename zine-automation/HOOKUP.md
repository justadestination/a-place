# HOOKUP — what connects to what

The zine automation is two **agent-executed** scheduled jobs. The scripts are
deterministic mechanics (Tier 3); the research, writing, humanizing, editing,
and gate judgment are agent work (Tier 1/2). A plain cron+script runner cannot
do this alone — the platform must schedule *agent runs* that follow the runbooks.

## What's in the box

```
zine-automation/
  README.md, SCHEDULER-SPEC.md, RUNBOOK.md, RUNBOOK-EDITOR.md, CIPHER.md (held)
  personas/      8 roster files, each with append-only "Stances taken" memory
  prompts/       hot-take, dossier, prediction, topic-overview, cartoon-brief,
                 humanize-pass, editor-pass, editors-letter (OPERATOR-OWNED)
  scripts/state.py   stdlib-only state helpers (gate/pick/topic/stance/
                     predict/log/publish/escalate)
  state/         state.json (seed) + run-log.md
  topics/_template/ + WORKFLOW.md
```

## Hookup 1 — Scheduler → jobs (the important one)

**What:** the platform's job runner must fire *agent* runs, not shell scripts.

| Job | Spec | Procedure | Cadence |
|---|---|---|---|
| `umwelt-horizons/writer-run` | SCHEDULER-SPEC.md §Job 1 | RUNBOOK.md | every 8h, ~40% gate/run |
| `umwelt-horizons/editor-run` | SCHEDULER-SPEC.md §Job 2 | RUNBOOK-EDITOR.md | every 8h, offset from writer |

**The agent runner needs:** filesystem read/write on this directory,
`python3` (stdlib only — `scripts/state.py` has no dependencies),
and **web search** for the research steps (news vertical for topic
discovery; general search for dossier/prediction verification).
Without web search the writer run cannot function — that step has no
script fallback.

**Interim:** both jobs currently run on Dexa's scheduler
(`zine-automation-run`, `zine-automation-editor`). Migration = implement
above, then disable Dexa's crons. Never double-run.

## Hookup 2 — `published/` → zine pipeline intake

**What:** every file the editor clears lands in `published/` as
**markdown + YAML frontmatter**, graph-ready.

**Frontmatter contract** (the pipeline can rely on these fields):

```yaml
title:    "..."            # headline
author:   "Name (screenname)"
persona:  "personas/<id>.md"
type:     stance | dossier-piece | prediction | cartoon-brief
prompt:   "prompts/<file>.md"
date:     YYYY-MM-DD
topic:    <slug>           # when tied to a news subject (links topics/)
stance:   "<one line>"     # when the piece takes one
status:   published
```

**Body convention:** `[[topic-slug]]` wikilinks → the pipeline converts these
to graph edges (per the zine content-modules contract: committed Markdown
appears as a graph node).

**Hookup:** point the pipeline's vault/content intake at `published/`
(or copy `published/*.md` into the vault on each editor run). Files are
immutable once published — corrections are new pieces, not edits.

## Hookup 3 — `topics/<slug>/` → graph nodes

Each topic is two nodes: `overview.md` (neutral cliff-notes) and
`full-report.md` (research dossier), cross-linked. Opinion pieces link to the
overview via `[[topic-slug]]`, producing piece→topic edges. Same intake as
Hookup 2 — the editor publishes topic files alongside the piece
(`state.py publish --draft <file> --topic <slug>` flips both).

## Hookup 4 — `needs-operator/` → operator inbox + alerting

**What:** anything the editor can't clear lands here with a reason
(unverifiable claims, defamation risk, punching-down ambiguity, stance
conflicts, legal/safety risk — or plain uncertainty).

**Now:** the editor run reports each escalation in chat (this is the 6.9
failure alert, interim version). the operator reads `needs-operator/` directly.

**When NightCal Boxes land:** escalations route to the **operator Box**
instead of (or as well as) the folder. The folder remains the fallback and
the audit trail. Until then, do not build a second notification path —
the chat report + folder is the whole system.

## Hookup 5 — `state.json`: single-writer rule

`state.json` + the persona `Stances taken` sections are the system's memory.
Exactly one runner writes at a time. If the platform ever parallelizes runs,
put a lock around `scripts/state.py` invocations. The script is idempotent
per command but not concurrency-safe.

## Hookup 6 — cipher slot (future, the operator-owned)

When the operator finishes the cipher scheme: spec goes in `CIPHER.md`; RUNBOOK.md
gains an **Embed cipher** step between Humanize (5) and Memory (6);
RUNBOOK-EDITOR.md gains a **verify the cipher solves** checkbox in the
copy-edit list. Nothing else changes. Do not invent a scheme in the meantime.

## Hookup 7 — keywords (optional)

`Keyword_Research_1min_AI_2026-10-09…xlsx` lives in `workspace/user/files/`
(not in this package). Only live row: "controversial news topics" (vol 140).
The hot-take prompt may weight toward it for SEO. Nothing to wire up —
it's a note, not a dependency.

## Manual run commands

```bash
cd zine-automation
python3 scripts/state.py gate --chance 40   # roll the gate (exit 3 = skip)
python3 scripts/state.py pick               # persona + prompt
python3 scripts/state.py topic <slug>       # record a new topic
python3 scripts/state.py stance --persona <id> --subject "..." --stance "..." --draft <file>
python3 scripts/state.py predict --persona <id> --claim "..." --check-date YYYY-MM-DD --draft <file>
python3 scripts/state.py publish --draft <file> [--topic <slug>]
python3 scripts/state.py escalate --draft <file> --reason "..."
python3 scripts/state.py log --persona <id> --prompt <type> --draft <file> [--notes "..."]
```

## Migration checklist (platform takeover)

- [ ] Agent runner scheduled: writer every 8h (+40% gate), editor every 8h offset
- [ ] Runner has fs access + python3 + web search
- [ ] `published/` wired to zine pipeline intake (Hookup 2)
- [ ] Escalation alert routed (chat now → operator Box later) (Hookup 4)
- [ ] Single-writer guarantee on state.json (Hookup 5)
- [ ] Dexa's interim crons (`zine-automation-run`, `zine-automation-editor`) disabled
- [ ] Cipher slotted in when the operator's scheme lands (Hookup 6)
