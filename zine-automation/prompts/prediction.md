# Prompt: The Forecast (prediction piece)

**For:** Priya, Mara, Juno, Mags
**Output:** 500–800 word article predicting something within the next year

## Setup

Use current events as hooks. The prediction must be *about the near future*
(within 12 months), specific enough to be checkable, and grounded in
verifiable present-day facts.

## Instructions

1. **Research first.** Web-search to verify every load-bearing claim about
   the present. A prediction built on a false premise is just fiction with
   confidence.
2. **One prediction per piece.** Not three vague trends — one concrete claim:
   "X will happen by [month]," with the mechanism that gets us there.
3. **Show the mechanism.** The reader should be able to follow the causal
   chain from today's verifiable facts to the predicted outcome. Name the
   forces, the incentives, the precedents.
4. **Calibrate.** State explicitly how confident the persona is and *why* —
   what would prove them wrong, what they're watching as the tell. Mara does
   this theatrically ("here's how I lose this bet"). Juno cites the base rates.
5. **The hook is current, the thinking is structural.** Don't just extrapolate
   the news cycle — find the slower force underneath it.
6. Persona voice throughout (Mags's image-openings, Priya's system-first
   explanations, Mara's debate-case structure).

## Hard rules (EDITORIAL_CHARTER.md)

- **Ground Truth Baseline (Rule 1):** Present-day claims must be 100% verified against real sources. Zero fabricated data, fake dockets, or phantom precedents.
- **Inference Out Loud (Rule 2):** Predictions are analytical projections, not established facts. Frame them explicitly: *"My inference from this trajectory is..."*, *"The causal model suggests..."*.
- **Mandatory Sources (Rule 3):** Dedicated `## Sources` section citing primary databases, official indicators, or reporting with working URLs.
- **Educational Intent (Rule 4):** The piece must educate the reader on the structural forces, mechanisms, or economic/technical dynamics driving the prediction.
- **Read-Time & Word Count (Rule 6):** 500–800 words (strict 5–6 min read limit, ceiling 1,400 words).
- **Backlink Chaining (Rule 7):** Connect to related topic files or dispatches using `[[wikilinks]]`.
- No predictions about named private individuals' fates, health, or legal outcomes.
- No election-outcome predictions presented as certainty — probabilities and mechanisms only.
- Every prediction gets logged in state.json with a check date. When the date
  arrives, a follow-up run scores it. Personas keep public scorecards — being
  wrong loudly is part of the bit.

## Done when

- [ ] One specific, checkable, dated prediction
- [ ] Mechanism fully shown; present-day baseline facts 100% verified
- [ ] Inferences explicitly identified out loud
- [ ] Dedicated `## Sources` section with active, working URLs
- [ ] Educational mechanism clear
- [ ] Word count within 500–800 words (≤ 1,400 words / 5–6 min read)
- [ ] Linked via `[[wikilinks]]` to related topic pages or dispatches
- [ ] Confidence stated with falsification conditions
- [ ] Logged in state.json with a check date
- [ ] Humanize pass applied; draft in `drafts/` with frontmatter
