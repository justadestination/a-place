/**
 * Venue Data Adapter & Helpers (Task 2.12).
 *
 * Provides:
 *   1. Normalization of venue profiles (active, closed, hiatus).
 *   2. Closed venue detection and event suppression (closed venues show status and list NO events).
 *   3. Contact info, address/map links, and directory (Yelp) resolution.
 *   4. Associated news blurbs and upcoming events aggregation.
 */

import { isClosedVenue } from "./calendar.js";

/**
 * Normalizes a raw venue object into a full VenueProfile.
 */
export function normalizeVenue(rawVenue, events = []) {
  if (!rawVenue) return null;

  const id = rawVenue.id || "";
  const name = rawVenue.name || "Unnamed Venue";
  const status = (rawVenue.status || "").toLowerCase() || (rawVenue.closed || rawVenue.is_closed ? "closed" : "active");
  const closed = isClosedVenue(rawVenue) || status === "closed" || status === "temporarily_closed";

  const contact = rawVenue.contact || {};
  const phones = contact.phones || [];
  const emails = contact.emails || [];
  const websites = contact.websites || [];
  const socials = contact.socials || [];

  // Directory links (e.g. Yelp, OSM)
  let yelpUrl = rawVenue.yelp || contact.yelp || null;
  if (!yelpUrl) {
    const yelpSocial = socials.find(s => (s.name || "").toLowerCase().includes("yelp") || (s.href || "").includes("yelp.com"));
    if (yelpSocial) yelpUrl = yelpSocial.href;
  }
  if (!yelpUrl) {
    const loc = rawVenue.address || "Santa Rosa";
    yelpUrl = `https://www.yelp.com/search?find_desc=${encodeURIComponent(name)}&find_loc=${encodeURIComponent(loc)}`;
  }

  // Map URL
  let mapUrl = null;
  if (rawVenue.lat && rawVenue.lon) {
    mapUrl = `https://www.openstreetmap.org/?mlat=${rawVenue.lat}&mlon=${rawVenue.lon}#map=17/${rawVenue.lat}/${rawVenue.lon}`;
  } else if (rawVenue.address) {
    mapUrl = `https://www.openstreetmap.org/search?query=${encodeURIComponent(rawVenue.address)}`;
  }

  // Blurbs / announcements
  const blurbs = rawVenue.blurbs || [
    {
      id: `blurb_${id}_1`,
      title: "Welcome to " + name,
      date: "2026-10-01",
      content: closed
        ? "This venue has concluded operations. Thank you to the community and artists for the memories."
        : "Check our upcoming calendar for shows, tickets, and community nights.",
    },
  ];

  // Upcoming events: if closed, strictly EMPTY list per specification
  const upcomingEvents = closed ? [] : events.filter(e => e.venueId === id);

  return {
    id,
    name,
    status,
    closed,
    address: rawVenue.address || "",
    lat: rawVenue.lat || null,
    lon: rawVenue.lon || null,
    mapUrl,
    yelpUrl,
    amenity: rawVenue.amenity || "",
    music: Boolean(rawVenue.music),
    timezone: rawVenue.timezone || "America/Los_Angeles",
    phones,
    emails,
    websites,
    socials,
    blurbs,
    events: upcomingEvents,
    merch_items: rawVenue.merch_items || rawVenue.merch || [],
    has_shop: Boolean(rawVenue.has_shop || (rawVenue.merch_items && rawVenue.merch_items.length)),
  };
}

/**
 * Lookup venue by id in calendar model or raw dataset.
 */
export function getVenueById(model, venueId) {
  if (!model || !venueId) return null;

  // Search in model.venues first
  let raw = (model.venues || []).find(v => v.id === venueId);
  // Also check raw venues array (which includes closed venues)
  if (!raw && model.raw?.venues) {
    raw = model.raw.venues.find(v => v.id === venueId);
  }

  if (!raw) return null;
  return normalizeVenue(raw, model.events || []);
}
