# Decision 005: Billboard Sizing Curve

- **Date:** 2026-10-08
- **Decider:** the operator
- **Status:** Approved

## Decision

1. **Sizing Model:**
   - Billboard slot area in the calendar and today page maps logarithmically to the attendance tally (`bodies`):
     ```
     size = clamp(min_size + k * ln(1 + max(0, bodies)), min_size, max_size)
     ```
2. **Parameters & Constraints:**
   - `min_size`: Baseline visual footprint ensuring legible typography and metadata even with zero votes (`bodies = 0`).
   - `k`: Logarithmic coefficient producing noticeable differentiation across low-to-medium turnout tiers (e.g. 5 vs 25 attendees).
   - `max_size`: Hard ceiling bounding box preventing viral or runaway popular events (e.g. 500+ bodies) from breaking the layout grid or obscuring adjacent community events.
3. **Outlier Verification:**
   - Confirmed resilient against runaway popular event edge cases; logarithmic decay prevents layout collapse.
