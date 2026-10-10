# Prompt: The Deep File (research dossier)

**For:** Juno (primary), Priya, Mags
**Output:** 800–1,300 word dossier (strict 5–6 minute read time; max 1,400 words) + source list. Feeds the topic workflow.

## Setup

Pick ONE subject: either the most controversial story of the last two weeks,
or the overlooked one — the story nobody noticed that's more important than
it looks. Prefer the overlooked one when it's genuinely substantive.

## Instructions (EDITORIAL_CHARTER.md)

1. **Become an expert in record time.** Exhaustive research: primary sources
   first (documents, filings, transcripts, data), then reporting from
   multiple outlets across the spectrum, then analysis. Minimum 8 distinct
   sources with active, verified URLs; note what each source's angle is. Zero fabricated facts or synthetic citations.
2. **Map the perspectives.** For each major viewpoint: who holds it, what
   evidence they cite, what they'd say the other side gets wrong. Steelman
   each one — the dossier is *not* the place for the persona's stance.
3. **Separate four layers explicitly:**
   - **Ground truth:** Verifiable facts, with working primary sources.
   - **Claims:** Assertions, attributed to who claims them.
   - **Inferences:** Any deduction or pattern analysis must be explicitly stated out loud (*"My inference from this is..."*).
   - **Unknowns:** Open questions, missing data, and what would settle them.
4. **Educational Intent:** Explain how the system, policy, or technical process works so the reader learns the mechanics.
5. **Write it as a dossier, not an essay.** Headed sections, tight paragraphs,
   a timeline if the story has one, a glossary if the jargon needs it.
6. **Read-Time & Word Count Gate:** Keep between 800 and 1,300 words (5–6 min read). Hard ceiling: 1,400 words.
7. **Backlink Chaining:** If the topic is vast, do NOT bloat into a single long wall of text. Decompose into modular sibling dispatches and chain them together using `[[wikilinks]]`.
8. The persona's voice colors the *prose*, not the *conclusions*. Juno's
   archival dryness, Priya's systems thinking, Mags's eye for the telling
   detail — but the facts stay neutral.

## Output

- The dossier itself → `topics/<slug>/full-report.md` (see topics/WORKFLOW.md)
- A cliff-notes overview → `topics/<slug>/overview.md` (see prompts/topic-overview.md)
- If the dossier was commissioned alongside a Stance piece, link them both ways via `[[wikilinks]]`.

## Done when

- [ ] 8+ distinct, verified sources with working URLs
- [ ] Ground truth only: zero fabricated records, dockets, or claims
- [ ] Four layers separated: facts, claims, inferences (explicitly stated), and unknowns
- [ ] Every perspective fairly stated (a holder of that view would recognize it)
- [ ] Word count within 800–1,300 words (≤ 1,400 word / 5–6 min read limit)
- [ ] Modular backlinks established via `[[wikilinks]]`
- [ ] Educational intent realized
- [ ] No stance taken — that's the Stance piece's job
- [ ] Both topic files written with frontmatter
