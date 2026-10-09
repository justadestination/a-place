# NightCal support channel plan (draft — task 7.6)

## The channel

Primary: a dedicated **support Box** in-app ("NightCal support"). Users send
Thoughts; Operators reply. This dogfoods the platform's own messaging instead
of bolting on a third-party helpdesk.

Fallback: email (address TBD — needs a decision, see open questions).

The Matrix room (Phase 5) can become the community support venue later; for
the test build the support Box is enough.

## Tiers

1. **Self-serve:** help docs (7.3), tooltips (7.2), walkthroughs (7.1).
2. **Support Box:** user asks, Operator (or a support Steward, later) answers.
3. **Escalation:** bug → filed against the repo with repro steps; abuse →
   operator review queue (ties into the Bodies pattern flags from 0.4);
   legal/safety → the operator directly.

## Response expectations (to publish)

- Support Box: best-effort, currently one human (the operator). Publish honest
  expectations — "usually within a day or two" beats a fake SLA.
- No phone support. No DMs to personal accounts.

## What support does NOT do

- No password resets — there are no passwords (identity is the Steward
  credential; recovery is Steward restore per 4.2).
- No backup recovery for regular accounts without a backup (per 0.9 policy).
- No content takedown without Operator review (community rules live
  front-and-center per Phase 7 scope).

## Open questions (the operator)

1. Fallback email address — new address or existing?
2. Does the support Box get a support Steward (auto-replies, triage), or
   human-only for the test build? (Human-only recommended to start.)
3. Published response-time wording.
