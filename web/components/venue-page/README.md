# Venue Page Component (`venue-page`)

Implements **Task 2.12: Venue pages**.

## Features
- **Dedicated Venue Profile**:
  - Venue name, street address, operating hours, phone, email, and OpenStreetMap directions link.
  - Directory integration (direct Yelp link).
  - Operator news blurbs and venue announcements.
- **Closed Venue Protection**:
  - Prominent status banner clearly identifying closed status ("Permanently Closed").
  - Strictly omits all upcoming events, rendering: *"No upcoming events scheduled. Venue is closed."*
- **Open Venue Schedule**:
  - Chronological list of upcoming events for this venue with lineup, start times, and direct event deep-links.
- **Accessibility & Design Tokens**:
  - 100% WCAG 2.2 AA compliant with 0 Axe violations.
  - Interactive touch targets >= 44px (`min-height: var(--nc-size-target)`).
  - Strictly 0 raw hex colors and 0 raw px units.
