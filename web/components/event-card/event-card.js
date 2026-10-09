import { h } from "../../js/core/dom.js";
import { kindTag } from "../kind-tag/kind-tag.js";
import { button } from "../button/button.js";
import { shareButton } from "../share-button/share-button.js";
import { label, relative } from "../../js/data/dates.js";
import { shareUrl } from "../../js/core/share.js";

let uid = 0;
const timeRange = e => [e.start, e.end].filter(Boolean).join(" – ");

/**
 * Everything about one event, and its one primary action: go to the listing.
 *   event   a CalendarModel event (js/data/calendar.js)
 *   venue   optional venue record for the address
 *   level   heading level (2 default; 3 inside lists)
 *   today   ISO date, for "Tonight"/"Tomorrow"
 */
export function eventCard(event, { venue, level = 2, today, showImage = true, shareHref } = {}) {
  const id = `nc-event-${++uid}`;
  const lineup = event.performers.filter(p => p.toLowerCase() !== event.title.toLowerCase());
  const when = `${today ? relative(event.date, today) : label.long(event.date)}${timeRange(event) ? ` · ${timeRange(event)}` : ""}`;
  const where = [event.venueName || "Venue not listed", venue?.address].filter(Boolean);
  const facts = h("dl.nc-event-card__facts", {},
    h("div", {}, h("dt", {}, "When"), h("dd", {}, when)),
    h("div", {}, h("dt", {}, "Where"), h("dd", {}, where.map((t, i) => (i ? [h("br"), t] : t)))),
    lineup.length ? h("div", {}, h("dt", {}, "Lineup"), h("dd", {}, lineup.join(", "))) : null,
  );
  const checks = event.checks.length
    ? h("p.nc-event-card__source", {}, `Listed by ${event.sourceName || "the downtown calendar"}. Also on `,
      event.checks.map((c, i) => [i ? ", " : "", h("a", { href: c.url, target: "_blank", rel: "noopener" }, c.name, h("span.nc-sr-only", {}, " (opens in a new tab)"))]), ".")
    : h("p.nc-event-card__source", {}, `Listed by ${event.sourceName || "the downtown calendar"}.`);
  const media = showImage && event.image
    ? h("div.nc-event-card__media", {}, h("img", { src: event.image, alt: `Listing image for ${event.title}`, loading: "lazy", decoding: "async", width: 640, height: 360 }))
    : null;
  return h("article.nc-event-card", { "aria-labelledby": id, "data-event-id": event.id },
    media,
    h("div.nc-event-card__body", {},
      kindTag(event.kind),
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
  summary: "One event in full: kind, title, when, where, lineup, sources, and the single primary action (the listing).",
  params: { id: "event id (defaults to the next night out)", image: "0 to hide the listing image" },
};

export async function embed(params, ctx) {
  const model = await ctx.calendar();
  const event = model.eventsById.get(params.get("id")) || model.events.find(e => e.night && e.date >= model.today) || model.events[0];
  if (!event) return h("p.nc-muted", {}, "No event found.");
  return eventCard(event, { venue: model.venuesById.get(event.venueId), today: model.today, showImage: params.get("image") !== "0" });
}
