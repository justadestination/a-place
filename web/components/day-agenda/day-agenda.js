import { h, emit } from "../../js/core/dom.js";
import { eventRow } from "../event-row/event-row.js";
import { button } from "../button/button.js";
import { relative, label, isValidDate } from "../../js/data/dates.js";
import { dayScene } from "../../js/data/scene.js";
import { filterEvents, nextDateWithEvents } from "../../js/data/calendar.js";

let uid = 0;
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

/**
 * The billboard: one night, every event on it, big.
 *   day      a day node from js/data/scene.js (dayScene/weekScene)
 *   today    ISO date for "Tonight"/"Tomorrow"
 *   next     ISO date of the next night with events (for the empty state)
 *   noun     "show"/"listing"
 * Fires nc-select {kind:"event", id} from rows and {kind:"day", date} from the empty-state jump.
 */
export function dayAgenda(day, { today, next = "", nextCount = 0, noun = "show", level = 2 } = {}) {
  const id = `nc-day-${++uid}`;
  const rel = relative(day.date, today);
  const headingText = rel === "Tonight" || rel === "Tomorrow" ? rel : label.long(day.date);
  const header = h("header.nc-day-agenda__header", {},
    h("p.nc-eyebrow", {}, rel === "Tonight" || rel === "Tomorrow" ? label.long(day.date) : label.monthYear(day.date.slice(0, 7))),
    h(`h${level}.nc-day-agenda__title`, { id }, headingText),
    h("p.nc-day-agenda__count", {}, day.events.length ? plural(day.events.length, noun, `${noun}s`) : `No ${noun}s listed`),
  );
  const section = h("section.nc-day-agenda", { "aria-labelledby": id, "data-date": day.date }, header);
  if (day.events.length) {
    section.append(h("ol.nc-day-agenda__list", { role: "list" }, day.events.map(e => h("li", {}, eventRow(e)))));
  } else {
    const empty = h("div.nc-day-agenda__empty", {}, h("p", {}, rel === "Tonight" ? "Nothing is listed for tonight yet." : "Nothing is listed for this night."));
    if (next) {
      const jump = button({ label: `Next: ${label.long(next)}${nextCount ? ` (${plural(nextCount, noun, `${noun}s`)})` : ""}`, variant: "secondary" });
      jump.addEventListener("click", () => emit(jump, "nc-select", { kind: "day", date: next }));
      empty.append(jump);
    }
    section.append(empty);
  }
  return section;
}

export const meta = {
  name: "day-agenda",
  title: "Day agenda",
  summary: "One night as a billboard: the date as a headline and every event as a large row. Has an empty state that jumps to the next night with events.",
  params: { date: "YYYY-MM-DD (defaults to today)", scope: "nights | all", venue: "venue id" },
};

export async function embed(params, ctx) {
  const model = await ctx.calendar();
  const date = isValidDate(params.get("date")) ? params.get("date") : model.today;
  const opts = { date, scope: params.get("scope") || "nights", venueId: params.get("venue") || "" };
  const day = dayScene(model, opts);
  const filtered = filterEvents(model, opts);
  const next = day.events.length ? "" : nextDateWithEvents(filtered, date);
  return dayAgenda(day, { today: model.today, next, nextCount: filtered.filter(e => e.date === next).length, noun: opts.scope === "all" ? "listing" : "show" });
}
