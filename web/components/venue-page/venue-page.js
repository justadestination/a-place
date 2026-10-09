/**
 * Venue Page Component (Task 2.12).
 *
 * Implements:
 *   1. Dedicated profile page per venue (name, address, hours, contact, map link, Yelp link).
 *   2. Closed venue banner & total omission of upcoming events when closed.
 *   3. Upcoming events feed when open.
 *   4. Operator news blurbs / announcements feed.
 *   5. Strict design tokens (0 raw hex, 0 raw px) and WCAG 2.2 AA target sizes (>= 44px).
 */

import { h } from "../../js/core/dom.js";
import { entityByName, entityHref, getEntity } from "../../js/data/entities.js";
import { button } from "../button/button.js";
import { getVenueById, normalizeVenue } from "../../js/data/venues.js";

export function mergeVenueOverlay(venue, overlay) {
  if (!overlay || typeof overlay !== "object") return venue;
  const next = { ...venue };
  if (overlay.name) next.name = overlay.name;
  if (overlay.address) next.address = overlay.address;
  if (Array.isArray(overlay.blurbs) && overlay.blurbs.length) {
    next.blurbs = overlay.blurbs.concat(venue.blurbs || []);
  }
  if (Array.isArray(overlay.events) && overlay.events.length) {
    const extras = overlay.events.map(event => ({
      id: event.id,
      title: event.title,
      date: event.date,
      start: event.start,
      venueId: venue.id,
      performers: event.performers || [],
    }));
    next.events = extras.concat(venue.events || []);
  }
  return next;
}

function lineupLinks(performers) {
  const row = h("p.nc-venue-event-item__lineup");
  performers.forEach((performer, index) => {
    if (index) row.append(" · ");
    const name = typeof performer === "string" ? performer : (performer?.name || "");
    const known = (performer && performer.id && getEntity(performer.id)) || entityByName(name);
    if (known) row.append(h("a.nc-entity-link", { href: entityHref(known) }, name));
    else row.append(name);
  });
  return row;
}

const DEFAULT_VENUE = {
  id: "ven_a261886187f23bb1",
  name: "Echo Music Hall",
  status: "active",
  closed: false,
  address: "120 5th Street, Santa Rosa",
  lat: 38.4383393,
  lon: -122.7199914,
  mapUrl: "https://www.openstreetmap.org/?mlat=38.4383393&mlon=-122.7199914#map=17/38.4383393/-122.7199914",
  yelpUrl: "https://www.yelp.com/biz/echo-music-hall-santa-rosa",
  contact: {
    phones: [{ text: "+1-707-542-1455", href: "tel:+17075421455" }],
    emails: [{ text: "booking@echomusichall.example", href: "mailto:booking@echomusichall.example" }],
    websites: [{ text: "echomusichall.example", href: "https://echomusichall.example" }],
  },
  blurbs: [
    {
      id: "blurb_1",
      title: "Fall Sound System Overhaul",
      date: "2026-10-01",
      content: "We've recalibrated our acoustic monitors and added extra low-frequency damping for crystal-clear live sets.",
    },
  ],
  events: [
    {
      id: "evt_seeded_1",
      title: "Subterranean Wave Syndicate",
      date: "2026-10-12",
      start: "8:00 PM",
      kind: "music",
      kindLabel: "Live music",
      performers: ["Wave Syndicate", "DJ Null"],
      bodies: 45,
    },
    {
      id: "evt_seeded_2",
      title: "Neon Horizon Sessions",
      date: "2026-10-19",
      start: "9:00 PM",
      kind: "music",
      kindLabel: "Live music",
      performers: ["Horizon Trio"],
      bodies: 60,
    },
  ],
};

export function venuePageView(options = {}) {
  const container = h("article.nc-venue-page", { "aria-labelledby": "nc-venue-title" });
  const venue = options.venue || DEFAULT_VENUE;
  const isClosed = Boolean(venue.closed || venue.status === "closed" || venue.status === "temporarily_closed");

  // 1. Header & Status Banner
  const eyebrow = h("p.nc-venue-page__eyebrow", {}, isClosed ? "Archived Venue Record" : "Live Music & Events Venue");
  const title = h("h1.nc-venue-page__title", { id: "nc-venue-title" }, venue.name);

  let statusBanner;
  if (isClosed) {
    statusBanner = h(
      "div.nc-venue-banner.nc-venue-banner--closed",
      { id: "nc-venue-status-banner", role: "status", "aria-label": "Venue status: Permanently closed" },
      h("strong.nc-venue-banner__badge", {}, "Permanently Closed"),
      h(
        "p.nc-venue-banner__text",
        {},
        "This venue has ceased public operations. No upcoming events are scheduled. Historical listings are preserved for archival record."
      )
    );
  } else {
    statusBanner = h(
      "div.nc-venue-banner.nc-venue-banner--active",
      { id: "nc-venue-status-banner", role: "status", "aria-label": "Venue status: Open and active" },
      h("strong.nc-venue-banner__badge", {}, "Open & Active"),
      h("p.nc-venue-banner__text", {}, "Currently hosting concerts, performances, and public events.")
    );
  }

  const header = h("header.nc-venue-page__header", {}, eyebrow, title, statusBanner);

  // 2. Profile Details & Contact Section
  const detailsList = h("dl.nc-venue-profile-grid", {});

  if (venue.address) {
    detailsList.appendChild(h("dt", {}, "Address"));
    const addressDd = h("dd.nc-venue-address", {}, venue.address);
    if (venue.mapUrl) {
      const mapBtn = h(
        "a.nc-button.nc-button--secondary.nc-venue-action-btn",
        {
          href: venue.mapUrl,
          target: "_blank",
          rel: "noopener noreferrer",
          "aria-label": `Open OpenStreetMap directions to ${venue.name}`,
        },
        "View on Map"
      );
      addressDd.appendChild(h("div.nc-venue-btn-wrapper", {}, mapBtn));
    }
    detailsList.appendChild(addressDd);
  }

  // Hours
  detailsList.appendChild(h("dt", {}, "Hours"));
  detailsList.appendChild(
    h("dd", {}, isClosed ? "Permanently closed" : (venue.hours || "Tue – Sun: 5:00 PM – 2:00 AM (Show nights)"))
  );

  // Contact
  const phones = (venue.contact?.phones || venue.phones || []);
  if (phones.length > 0) {
    detailsList.appendChild(h("dt", {}, "Phone"));
    const phoneList = h("dd", {});
    for (const p of phones) {
      phoneList.appendChild(h("a.nc-venue-link", { href: p.href || `tel:${p.text}` }, p.text));
    }
    detailsList.appendChild(phoneList);
  }

  const emails = (venue.contact?.emails || venue.emails || []);
  if (emails.length > 0) {
    detailsList.appendChild(h("dt", {}, "Email"));
    const emailList = h("dd", {});
    for (const em of emails) {
      emailList.appendChild(h("a.nc-venue-link", { href: em.href || `mailto:${em.text}` }, em.text));
    }
    detailsList.appendChild(emailList);
  }

  // Directory / Yelp link
  if (venue.yelpUrl) {
    detailsList.appendChild(h("dt", {}, "Directory"));
    const yelpLink = h(
      "a.nc-button.nc-button--ghost.nc-venue-action-btn.nc-venue-yelp-link",
      {
        id: "nc-venue-yelp-link",
        href: venue.yelpUrl,
        target: "_blank",
        rel: "noopener noreferrer",
        "aria-label": `Visit Yelp reviews and community photos for ${venue.name}`,
      },
      "Yelp Directory"
    );
    detailsList.appendChild(h("dd", {}, yelpLink));
  }

  const profileSection = h(
    "section.nc-venue-section",
    { "aria-labelledby": "nc-profile-heading" },
    h("h2.nc-venue-section__title", { id: "nc-profile-heading" }, "Venue Profile & Details"),
    detailsList
  );

  // 3. News Blurbs / Announcements Section
  const blurbs = venue.blurbs || [];
  const blurbsContainer = h("div.nc-venue-blurbs-list", { id: "nc-venue-blurbs" });
  if (blurbs.length === 0) {
    blurbsContainer.appendChild(h("p.nc-venue-empty-text", {}, "No announcements currently posted."));
  } else {
    for (const b of blurbs) {
      blurbsContainer.appendChild(
        h(
          "article.nc-venue-blurb-card",
          {},
          h("h3.nc-venue-blurb-card__title", {}, b.title),
          h("time.nc-venue-blurb-card__date", { dateTime: b.date }, new Date(b.date).toLocaleDateString()),
          h("p.nc-venue-blurb-card__content", {}, b.content)
        )
      );
    }
  }

  const blurbsSection = h(
    "section.nc-venue-section",
    { "aria-labelledby": "nc-blurbs-heading" },
    h("h2.nc-venue-section__title", { id: "nc-blurbs-heading" }, "News & Announcements"),
    blurbsContainer
  );

  // 4. Upcoming Events Section (CLOSED VENUES LIST ZERO EVENTS)
  const eventsContainer = h("div.nc-venue-events-container", { id: "nc-venue-events" });
  const events = isClosed ? [] : (venue.events || []);

  if (isClosed) {
    eventsContainer.appendChild(
      h(
        "div.nc-venue-no-events.nc-venue-no-events--closed",
        { id: "nc-venue-no-events", role: "status" },
        "No upcoming events scheduled. Venue is closed."
      )
    );
  } else if (events.length === 0) {
    eventsContainer.appendChild(
      h(
        "div.nc-venue-no-events",
        { id: "nc-venue-no-events" },
        "No upcoming events currently scheduled. Check back soon for new dates."
      )
    );
  } else {
    const eventsList = h("ul.nc-venue-events-list", { "aria-label": `Upcoming events at ${venue.name}` });
    for (const ev of events) {
      const item = h(
        "li.nc-venue-event-item",
        {},
        h(
          "div.nc-venue-event-item__time",
          {},
          h("span.nc-venue-event-item__date", {}, ev.date),
          h("span.nc-venue-event-item__clock", {}, ev.start || "Evening")
        ),
        h(
          "div.nc-venue-event-item__main",
          {},
          h("h3.nc-venue-event-item__title", {}, ev.title),
          ev.performers && ev.performers.length > 0
            ? lineupLinks(ev.performers)
            : null
        ),
        h(
          "div.nc-venue-event-item__action",
          {},
          h(
            "a.nc-button.nc-button--primary.nc-venue-action-btn",
            {
              href: `/today#${ev.id}`,
              "aria-label": `View event details for ${ev.title}`,
            },
            "Details"
          )
        )
      );
      eventsList.appendChild(item);
    }
    eventsContainer.appendChild(eventsList);
  }

  const eventsSection = h(
    "section.nc-venue-section",
    { "aria-labelledby": "nc-events-heading" },
    h("h2.nc-venue-section__title", { id: "nc-events-heading" }, "Upcoming Events"),
    eventsContainer
  );

  container.appendChild(header);
  container.appendChild(profileSection);
  container.appendChild(blurbsSection);
  container.appendChild(eventsSection);

  return container;
}

export async function embed(params = new URLSearchParams(), ctx = {}) {
  let venueId = params.get("id") || params.get("venue");
  let venue = null;

  if (ctx.calendar) {
    try {
      const model = await ctx.calendar();
      if (!venueId) {
        const withEvents = (model.venues || []).find(v => (model.events || []).some(e => e.venueId === v.id));
        venueId = withEvents ? withEvents.id : (model.venues[0]?.id || "ven_47b8847d9089d868");
      }
      venue = getVenueById(model, venueId);
    } catch {
      venue = null;
    }
  }

  // Seeded mock for closed venue testing via parameter ?closed=1
  if (params.get("closed") === "1" || venueId === "v_closed_sample") {
    venue = normalizeVenue({
      id: "v_closed_sample",
      name: "The Velvet Cellar (Closed)",
      status: "closed",
      closed: true,
      address: "700 Main Street, Santa Rosa",
      yelp: "https://www.yelp.com/biz/the-velvet-cellar",
      blurbs: [
        {
          id: "b_closed",
          title: "Permanent Closure Notice",
          date: "2026-09-01",
          content: "The Velvet Cellar permanently closed its doors on September 1, 2026. All scheduled events have ended.",
        },
      ],
    }, []);
  }

  if (!venue && venueId) {
    venue = { id: venueId, name: "Venue", status: "active", address: "", blurbs: [], events: [], contact: {} };
  }
  if (!venue) {
    venue = DEFAULT_VENUE;
  }
  if (venueId && params.get("closed") !== "1") {
    try {
      const resp = await fetch(`/api/venues/edit?id=${encodeURIComponent(venueId)}`);
      if (resp.ok) venue = mergeVenueOverlay(venue, await resp.json());
    } catch {
      /* The static venue still renders when the edit API is down. */
    }
  }

  return venuePageView({ venue });
}
