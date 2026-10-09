import { h } from "../../js/core/dom.js";
import { kindTag } from "../kind-tag/kind-tag.js";
import { button } from "../button/button.js";
import { shareButton } from "../share-button/share-button.js";
import { label, relative } from "../../js/data/dates.js";
import { shareUrl } from "../../js/core/share.js";

let uid = 0;
const timeRange = e => [e.start, e.end].filter(Boolean).join(" – ");

/**
 * Decision 005: Billboard sizing curve:
 *   size = clamp(min_size + k * ln(1 + max(0, bodies)), min_size, max_size)
 *
 * Parameters:
 *   minSize: 1.0 (baseline visual footprint ensuring legible typography at 0 bodies)
 *   k: 0.082 (logarithmic coefficient producing clear differentiation for 5 vs 25 vs 100 bodies)
 *   maxSize: 1.75 (hard ceiling bounding box preventing runaway viral events from swallowing the page)
 */
export function billboardScale(bodies, { minSize = 1.0, maxSize = 1.75, k = 0.082 } = {}) {
  const n = Math.max(0, Number(bodies) || 0);
  const size = minSize + k * Math.log(1 + n);
  return Math.min(maxSize, Math.max(minSize, size));
}

/**
 * Everything about one event, and its one primary action: go to the listing.
 *   event   a CalendarModel event (js/data/calendar.js)
 *   venue   optional venue record for the address
 *   level   heading level (2 default; 3 inside lists)
 *   today   ISO date, for "Tonight"/"Tomorrow"
 */
export function eventCard(event, { venue, level = 2, today, showImage = true, shareHref } = {}) {
  const id = `nc-event-${++uid}`;
  const bodies = Math.max(0, Number(event.bodies ?? event.up ?? 0));
  const scale = billboardScale(bodies);
  const scaleStr = scale.toFixed(3);
  const lineup = event.performers.filter(p => p.toLowerCase() !== event.title.toLowerCase());
  const when = `${today ? relative(event.date, today) : label.long(event.date)}${timeRange(event) ? ` · ${timeRange(event)}` : ""}`;
  const where = [event.venueName || "Venue not listed", venue?.address].filter(Boolean);
  const facts = h("dl.nc-event-card__facts", {},
    h("div", {}, h("dt", {}, "When"), h("dd", {}, when)),
    h("div", {}, h("dt", {}, "Where"), h("dd", {}, where.map((t, i) => (i ? [h("br"), t] : t)))),
    h("div", {}, h("dt", {}, "Attendance"), h("dd", {}, `${bodies} ${bodies === 1 ? "body" : "bodies"}`)),
    lineup.length ? h("div", {}, h("dt", {}, "Lineup"), h("dd", {}, lineup.join(", "))) : null,
  );
  const checks = event.checks.length
    ? h("p.nc-event-card__source", {}, `Listed by ${event.sourceName || "the downtown calendar"}. Also on `,
      event.checks.map((c, i) => [i ? ", " : "", h("a", { href: c.url, target: "_blank", rel: "noopener" }, c.name, h("span.nc-sr-only", {}, " (opens in a new tab)"))]), ".")
    : h("p.nc-event-card__source", {}, `Listed by ${event.sourceName || "the downtown calendar"}.`);
  const media = showImage && event.image
    ? h("div.nc-event-card__media", {}, h("img", { src: event.image, alt: `Listing image for ${event.title}`, loading: "lazy", decoding: "async", width: 640, height: 360 }))
    : null;

  const gauge = h("span.nc-event-card__gauge", { "aria-label": `${bodies} intended attendance` },
    h("span.nc-event-card__gauge-count", {}, `${bodies}`),
    h("span.nc-event-card__gauge-label", {}, ` ${bodies === 1 ? "body" : "bodies"}`),
  );

  return h("article.nc-event-card", {
    "aria-labelledby": id,
    "data-event-id": event.id,
    "data-bodies": String(bodies),
    "data-scale": scaleStr,
    style: `--nc-card-scale: ${scaleStr};`,
  },
    media,
    h("div.nc-event-card__body", {},
      h("div.nc-event-card__meta", {}, kindTag(event.kind), gauge),
      h(`h${level}.nc-event-card__title`, { id }, event.title),
      facts,
      checks,
      h("div.nc-event-card__actions", {},
        event.url ? button({ label: "Event page", variant: "primary", href: event.url, external: true }) : null,
        shareButton({ title: event.title, text: `${event.title} — ${when}${event.venueName ? `, ${event.venueName}` : ""}`, url: shareHref || shareUrl(`/?date=${event.date}&event=${encodeURIComponent(event.id)}`) }),
      ),
    ),
  );
}

export const meta = {
  name: "event-card",
  title: "Event card",
  summary: "One event in full: kind, title, when, where, lineup, sources, attendance gauge scaled by billboard curve, and the single primary action (the listing).",
  params: {
    id: "event id (defaults to the next night out)",
    image: "0 to hide the listing image",
    bodies: "override bodies attendance tally (for testing the billboard curve)",
  },
};

export async function embed(params, ctx) {
  const model = await ctx.calendar();
  let event = model.eventsById.get(params.get("id")) || model.events.find(e => e.night && e.date >= model.today) || model.events[0];
  if (!event) return h("p.nc-muted", {}, "No event found.");
  if (params.has("bodies")) {
    event = { ...event, bodies: parseInt(params.get("bodies"), 10) || 0 };
  }
  return eventCard(event, { venue: model.venuesById.get(event.venueId), today: model.today, showImage: params.get("image") !== "0" });
}
