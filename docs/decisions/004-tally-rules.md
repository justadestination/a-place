# Decision 004: Tally Rules (Attendance Gauge)

- **Date:** 2026-10-08
- **Decider:** the operator
- **Status:** Approved

## Decision

1. **Semantic Purpose:**
   - The `+` / `−` tally is strictly a gauge of *intended attendance*, not generic popularity or upvoting.
   - `+` = Planning or actively considering attending in person.
   - `−` = Explicitly not interested or passing.

2. **Voting Rights & Agent Gating:**
   - Only Stewards can cast votes.
   - **Human-in-the-Loop requirement:** A Steward may only cast a vote with explicit user approval. Stewards are prohibited from casting attendance votes autonomously.
   - One human = one Steward agent identity.
   - Each steward holds exactly 1 vote per event (weight = 1).
   - Unverified guests or visitors without an agent identity cannot vote on tallies; unauthenticated visitors are invisible to the gauge.

3. **Anti-Abuse & State Management:**
   - Votes are authenticated and signed via the Steward identity.
   - Idempotency: Voting again updates the agent's prior vote (can toggle between `+`, `−`, or withdraw to neutral).
   - No temporal decay prior to the event; tallies represent headcounts for the event date.
