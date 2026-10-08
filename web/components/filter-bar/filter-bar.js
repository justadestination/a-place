import { h, emit } from "../../js/core/dom.js";
import { SCOPES, roomsWithEvents } from "../../js/data/calendar.js";

let uid = 0;

/**
 * Two plain filters: what kind of listings (segmented radio) and which room
 * (native select). Only rooms with something on are offered, so closed rooms
 * never show up as choices. Fires nc-filter { scope, venueId }.
 */
export function filterBar({ scope = "nights", venueId = "", rooms = [] } = {}) {
  const id = ++uid;
  const form = h("form.nc-filters", { "aria-label": "Filter events", onsubmit: e => e.preventDefault() });
  const seg = h("fieldset.nc-segmented", {},
    h("legend.nc-label", {}, "Show"),
    h("div.nc-segmented__options", {}, Object.entries(SCOPES).map(([value, text]) =>
      h("label.nc-segmented__option", {},
        h("input", { type: "radio", name: `scope-${id}`, value, checked: value === scope }),
        h("span", {}, text)))),
  );
  const select = h("select.nc-select", { id: `nc-room-${id}`, name: "venue" },
    h("option", { value: "" }, "All rooms"),
    rooms.map(r => h("option", { value: r.id, selected: r.id === venueId }, r.name)),
  );
  form.append(seg, h("div.nc-filters__room", {}, h("label.nc-label", { for: `nc-room-${id}` }, "Room"), select));
  form.addEventListener("change", () => {
    emit(form, "nc-filter", { scope: form.querySelector(`input[name="scope-${id}"]:checked`)?.value || "nights", venueId: select.value });
  });
  return form;
}

export const meta = {
  name: "filter-bar",
  title: "Filter bar",
  summary: "Nights out vs everything, and one room. Native radios and select, so keyboard and screen readers work without extra code. Emits nc-filter.",
  params: { scope: "nights | all", venue: "venue id" },
};

export async function embed(params, ctx) {
  const model = await ctx.calendar();
  const scope = params.get("scope") || "nights";
  const bar = filterBar({ scope, venueId: params.get("venue") || "", rooms: roomsWithEvents(model, { scope: "all" }) });
  bar.addEventListener("nc-filter", e => ctx.select("filter", "", e.detail));
  return bar;
}
