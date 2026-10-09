# Decision 003: Daily Summary Source & Synthesis

- **Date:** 2026-10-08
- **Decider:** the operator
- **Status:** Approved

## Decision

1. **Source of Truth:**
   - The daily syndicated summary is synthesized directly from the scheduled calendar events (`spots`) registered for that specific day.
   - Sourced entirely from the NightCal calendar database for the target date.

2. **Synthesis & Refresh:**
   - Summaries dynamically digest what is taking place across the city/venues for that calendar date.
   - Re-evaluated and refreshed whenever day calendar spots are added, updated, or purged.

3. **Fallback & Resiliency:**
   - If no events are registered for a given date, the UI renders a clean, quiet empty state ("No events logged for tonight").
   - Completely local and self-contained within ShadeNet / NightCal; zero reliance on fragile external third-party syndication APIs or web scrapers.
