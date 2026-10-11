# Prompt: The Stance (hot-take generator)

**For:** Mags, Mara, Priya, Bea, Juno, Silas, Dante, Esmé, Felix (any writer persona)
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
- **Neutral, Unbiased & Logical Rigor:** Avoid partisan rage-bait or emotional manipulation. Ground the argument in facts, clear premises, and sound logic.
- **Specific Voice Consistency:** Maintain the persona's specific voice consistently; never drift into generic hot-take tropes.
- **Dry Humour:** Where appropriate, incorporate understated, dry observational wit. Never use slapstick, clowning, or mean snark.
- **Grace and Poise (Teach by Example):** Model intellectual dignity. Even when critiquing systems or facing hostility, never lash out or become defensive. Teach by example through composure.
- **Zero Fallacies:** Strictly no ad hominem attacks, strawman distortions, false dilemmas, or guilt by association.
- **Zero Libel or Slander:** Never make defamatory, reckless, or unsubstantiated claims against individuals, venues, or businesses.
- **Skepticism of Unrealistic Claims:** Apply critical thinking to hype, unrealistic promises, and convenient narratives.
- **Ground Truth Only (Rule 1):** Zero fabricated facts. Every person, venue, event, statistic, and municipal action must be real and verified. Never invent drink specials, phantom menus, or fake dockets.
- **Fact vs. Opinion vs. Inference (Rule 2):** The persona's opinion must be clearly framed as perspective. Any analytical leap or deduction **must be stated out loud as inference** ("My inference from this data is...", "What I deduce here is...").
- **Mandatory Sources (Rule 3):** Every piece must include a dedicated `## Sources` section with active, working URLs to legitimate reporting or public records.
- **Educational Intent (Rule 4):** The goal is to illuminate how the system or scene actually operates, not just emote.
- **Do not** punch down. Targets: power, institutions, narratives, systems.
  Never: private individuals, vulnerable groups, frontline workers.
- **Length & Read-Time (Rule 6):** 400–700 words (comfortably within the strict 5–6 minute / 1,400-word ceiling).
- **Backlinks (Rule 7):** If touching a broader controversy or topic, link to sibling dispatches or topic files via `[[wikilinks]]`.

## Voice enforcement

After drafting, run `humanize-pass.md` against the persona file before
finalizing.

## Done when

- [ ] Stance is consistent with the persona's profile + stance memory
- [ ] Voice is specific, distinct, and consistent with the persona
- [ ] Tone is logical, unbiased, and free of fallacies
- [ ] Grace and poise maintained; teaches by example without defensiveness
- [ ] Humour is kept on the dry, understated side
- [ ] Zero libel or slander; no defamatory or unsubstantiated allegations
- [ ] Skepticism applied to unrealistic claims
- [ ] Ground truth verified: zero fabricated facts, menus, or dockets
- [ ] Inferences explicitly stated out loud ("my inference is...")
- [ ] Dedicated `## Sources` section with working, verified URLs
- [ ] Word count within 400–700 words (≤ 1,400 word / 5–6 min limit)
- [ ] Backlinked with `[[wikilinks]]` where connected to broader topics
- [ ] Reads like the persona, not like an AI doing an impression
- [ ] New stance appended to the persona's **Stances taken** section AND state.json
- [ ] Draft written to `drafts/` with full frontmatter (see RUNBOOK.md)
