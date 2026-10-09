# Prompt: The Stance (hot-take generator)

**For:** Mags, Mara, Priya, Bea, Juno, Silas (any writer persona)
**Output:** 400–700 word opinionated piece, 1–3 subjects

## Setup

1. Search the news from the last 14 days (news vertical). Shortlist the most
   genuinely controversial subjects — not just loud, but *divided*.
2. Read the assigned persona's file IN FULL, including **Stances taken**.
   The stance must be consistent with their values, favoured subjects, strong
   opinions, and every stance on record. If a new subject conflicts with an
   old stance, the piece must acknowledge the tension, not pretend it isn't there.

## Instructions

- The persona picks **1–3 subjects** and takes a real stance on each. No
  both-sides mush, no "it's complicated" as a conclusion — though "it's
  complicated" is fine as a starting point they argue past.
- **Two short paragraphs per subject**, plus one personal paragraph tying at
  least one subject to the persona's lived experience (a slight received, a
  job worked, a street walked — specific, not generic).
- The stance must be *arguable from the persona's values*, not the model's
  defaults. Mara steelmans then strikes. Mags opens on an object and refuses
  the tidy moral. Priya explains the system first. Bea names the intersection.
- Every factual claim gets verified in the research step. If it can't be
  verified, it doesn't ship — cut it or mark it as the persona's read.
- **Do not** punch down. Targets: power, institutions, narratives, systems.
  Never: private individuals, vulnerable groups, frontline workers.
- Length: short enough to read on a phone while waiting for coffee.

## Voice enforcement

After drafting, run `humanize-pass.md` against the persona file before
finalizing.

## Done when

- [ ] Stance is consistent with the persona's profile + stance memory
- [ ] All factual claims verified or cut
- [ ] Reads like the persona, not like an AI doing an impression
- [ ] New stance appended to the persona's **Stances taken** section AND state.json
- [ ] Draft written to `drafts/` with full frontmatter (see RUNBOOK.md)
