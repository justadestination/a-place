# Venue Pages Architecture

**Status:** Completed & Verified (Task 2.12)  
**Specification:** `nightcal-master-todo.md` Section 2.12

---

## 1. Overview & Requirements

Every venue recognized in NightCal has a dedicated page providing:
1. **Venue Profile**:
   - Canonical name, street address, operating hours, and localized timezone.
   - Contact links: telephone (`tel:`), booking email (`mailto:`), and official website.
   - Directory navigation: direct Yelp link (`yelpUrl`) and OpenStreetMap directions (`mapUrl`).
2. **Closed Venue Protection**:
   - Status determination via `isClosedVenue(v)` and schema `status` lifecycle (`active`, `closed`, `temporarily_closed`).
   - Prominent accessible banner alerting patrons that the venue is permanently closed.
   - **Zero Event Listing Guarantee**: Closed venues strictly suppress all upcoming events, rendering:
     *"No upcoming events scheduled. Venue is closed."*
3. **Open Venue Schedule**:
   - Real-time aggregation of upcoming shows and performances for that venue with lineup, start times, and direct calendar deep-links.
4. **Operator News Blurbs & Announcements**:
   - Blurb feed for venue management to communicate sound system upgrades, ticket releases, or door policies.

---

## 2. Component & Routes Architecture

- **Dedicated Page**: `/venue/?id=<venue_id>` (and `/venue/index.html`)
- **Standalone Embed Route**: `/embed/venue-page/?id=<venue_id>&closed=<0|1>`
- **Component**: `web/components/venue-page/` (`venue-page.js`, `venue-page.css`, `README.md`)
- **Data Adapter**: `web/js/data/venues.js` (`normalizeVenue`, `getVenueById`)

---

## 3. Accessibility & Design Token Discipline

- 100% WCAG 2.2 AA compliance verified across Phone, Tablet, and Desktop viewports with 0 Axe violations.
- Interactive targets (buttons, links, map triggers) strictly enforce `min-height: var(--nc-size-target)` (>= 44px).
- Zero raw hex colors and zero raw px units in component stylesheet.
