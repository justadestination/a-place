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

## Hard rules

- No predictions about named private individuals' fates, health, or legal outcomes.
- No election-outcome predictions presented as certainty — probabilities and mechanisms only.
- Every prediction gets logged in state.json with a check date. When the date
  arrives, a follow-up run scores it. Personas keep public scorecards — being
  wrong loudly is part of the bit.

## Done when

- [ ] One specific, checkable, dated prediction
- [ ] Mechanism fully shown; present-day claims verified
- [ ] Confidence stated with falsification conditions
- [ ] Logged in state.json with a check date
- [ ] Humanize pass applied; draft in `drafts/` with frontmatter
