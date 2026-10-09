import { h, emit } from "../../js/core/dom.js";
import { billboardScale } from "../event-card/event-card.js";
import { kindTag } from "../kind-tag/kind-tag.js";
import { button } from "../button/button.js";
import { shareButton } from "../share-button/share-button.js";
import { shareUrl } from "../../js/core/share.js";
import { label, relative, isValidDate } from "../../js/data/dates.js";
import { dayScene } from "../../js/data/scene.js";

let uid = 0;
const timeRange = e => [e.start, e.end].filter(Boolean).join(" – ");

/**
 * Task 2.4: Today page — the road timeline.
 * Chronological "road into the distance":
 *   - Position = start time (nearest upcoming event appears first / visually nearest).
 *   - Box size = expected attendance (the +/− gauge via billboardScale).
 *   - Tie-breaker: events at same start time ordered by expected attendance (bodies).
 *   - Matches concept: next-up event is visually nearest; later-but-hotter event is further yet bigger.
 */
/** Pure: sort events chronologically by start time, tie-broken by bodies attendance */
export function sortRoadEvents(events) {
  return [...(events || [])].sort((a, b) => {
    const minA = Number.isFinite(a.minutes) ? a.minutes : 24 * 60;
    const minB = Number.isFinite(b.minutes) ? b.minutes : 24 * 60;
    if (minA !== minB) return minA - minB;
    const bodA = Math.max(0, Number(a.bodies ?? a.up ?? 0));
    const bodB = Math.max(0, Number(b.bodies ?? b.up ?? 0));
    if (bodB !== bodA) return bodB - bodA;
    return (a.title || "").localeCompare(b.title || "");
  });
}

export function roadTimeline(events, { today, level = 2, showImage = false } = {}) {
  const list = h("ol.nc-road-timeline", { role: "list" });

  if (!events || events.length === 0) {
    return list;
  }

  const sorted = sortRoadEvents(events);

  for (const event of sorted) {
    const cardId = `nc-road-event-${++uid}`;
    const bodies = Math.max(0, Number(event.bodies ?? event.up ?? 0));
    const scale = billboardScale(bodies);
    const scaleStr = scale.toFixed(3);
    const when = `${today ? relative(event.date, today) : label.long(event.date)}${timeRange(event) ? ` · ${timeRange(event)}` : ""}`;
    const lineup = (event.performers || []).filter(p => p.toLowerCase() !== (event.title || "").toLowerCase());

    const facts = h("dl.nc-event-card__facts", {},
      h("div", {}, h("dt", {}, "When"), h("dd", {}, when)),
      h("div", {}, h("dt", {}, "Where"), h("dd", {}, event.venueName || "Venue not listed")),
      h("div", {}, h("dt", {}, "Attendance"), h("dd", {}, `${bodies} ${bodies === 1 ? "body" : "bodies"}`)),
      lineup.length ? h("div", {}, h("dt", {}, "Lineup"), h("dd", {}, lineup.join(", "))) : null,
    );

    const checks = event.checks && event.checks.length
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

    const card = h("article.nc-road__card.nc-event-card", {
      "aria-labelledby": cardId,
      "data-event-id": event.id,
      "data-bodies": String(bodies),
      "data-scale": scaleStr,
      "data-start": event.start || "All day",
      "data-minutes": String(Number.isFinite(event.minutes) ? event.minutes : 24 * 60),
      style: `--nc-card-scale: ${scaleStr}; cursor: pointer;`,
    },
      media,
      h("div.nc-event-card__body", {},
        h("div.nc-event-card__meta", {}, kindTag(event.kind), gauge),
        h(`h${level}.nc-event-card__title`, { id: cardId }, event.title),
        facts,
        checks,
        h("div.nc-event-card__actions", {},
          event.url ? button({ label: "Event page", variant: "primary", href: event.url, external: true }) : null,
          shareButton({ title: event.title, text: `${event.title} — ${when}${event.venueName ? `, ${event.venueName}` : ""}`, url: shareUrl(`/?date=${event.date}&event=${encodeURIComponent(event.id)}`) }),
        ),
      ),
    );

    card.addEventListener("click", ev => {
      if (ev.target.closest("button, a")) return;
      emit(card, "nc-select", { kind: "event", id: event.id });
    });

    const timeBadge = h("div.nc-road__milestone", { "aria-hidden": "true" },
      h("span.nc-road__dot"),
      h("span.nc-road__time", {}, event.start || "All day"),
    );

    const stop = h("li.nc-road__stop", {
      "data-start": event.start || "All day",
      "data-minutes": String(Number.isFinite(event.minutes) ? event.minutes : 24 * 60),
    }, timeBadge, card);

    list.append(stop);
  }

  return list;
}

export const meta = {
  name: "road-timeline",
  title: "Road timeline",
  summary: "Chronological road into the distance for today's events: position = start time, box size = attendance gauge.",
  params: { date: "YYYY-MM-DD (defaults to today)", scope: "nights | all", venue: "venue id" },
};

export async function embed(params, ctx) {
  const model = await ctx.calendar();
  const date = isValidDate(params.get("date")) ? params.get("date") : model.today;
  const opts = { date, scope: params.get("scope") || "nights", venueId: params.get("venue") || "" };
  const day = dayScene(model, opts);
  return roadTimeline(day.events, { today: model.today, noun: opts.scope === "all" ? "listing" : "show" });
}
