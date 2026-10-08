import { h, emit } from "../../js/core/dom.js";
import { kindTag } from "../kind-tag/kind-tag.js";

/**
 * One event as a single big tap target: time, title, room, kind.
 * Activating it fires "nc-select" { kind: "event", id } on the row.
 */
export function eventRow(event, { showDate = false, dateLabel = "" } = {}) {
  const row = h("button.nc-event-row", { type: "button", "data-event-id": event.id },
    h("span.nc-event-row__time", {}, showDate && dateLabel ? h("span.nc-event-row__date", {}, dateLabel) : null, event.start || "All day"),
    h("span.nc-event-row__main", {},
      h("span.nc-event-row__title", {}, event.title),
      h("span.nc-event-row__venue", {}, event.venueName || "Venue not listed"),
    ),
    h("span.nc-event-row__kind", {}, kindTag(event.kind, { compact: true })),
  );
  row.addEventListener("click", () => emit(row, "nc-select", { kind: "event", id: event.id }));
  return row;
}

export const meta = {
  name: "event-row",
  title: "Event row",
  summary: "A list item for one event: time, title, room and kind in one 44px+ target. Emits nc-select.",
  params: { id: "event id (defaults to the next night out)" },
};

export async function embed(params, ctx) {
  const model = await ctx.calendar();
  const event = model.eventsById.get(params.get("id")) || model.events.find(e => e.night && e.date >= model.today) || model.events[0];
  return event ? eventRow(event) : h("p.nc-muted", {}, "No event found.");
}
