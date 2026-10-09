# Topic workflow

Every news subject the zine touches gets a **topic**: a neutral cliff-notes
overview plus the full research report attached. Opinion pieces link to the
topic; the topic never takes a side.

## When to create a topic

A run touches a news subject → check `state.json` → if the subject has no
topic yet, create one **before** writing the opinion piece. The Stance piece
then links to the overview ("the zine's neutral breakdown is here").

One subject = one topic. If a later piece touches the same subject, link the
existing topic; update it only if the facts materially changed.

## Directory layout

```
topics/<slug>/
  overview.md      — cliff-notes (prompts/topic-overview.md)
  full-report.md   — the dossier (prompts/dossier.md)
```

Slug: lowercase, hyphenated, e.g. `cecot-deportations-2026-10`.

## Frontmatter (both files)

```yaml
---
title: "..."
topic: <slug>
type: topic-overview | topic-report
date: YYYY-MM-DD
sources: <count>   # full-report only
status: draft
---
```

## Cross-linking

- `overview.md` links to `full-report.md` ("Go deeper").
- `full-report.md` links back to `overview.md`.
- Every opinion piece on the subject links to the overview.
- Use `[[topic-slug]]` wikilink style in body text — the zine pipeline
  converts these to graph edges.
