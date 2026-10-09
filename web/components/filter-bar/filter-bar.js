import { h, emit } from "../../js/core/dom.js";
import { SCOPES, roomsWithEvents, kindsWithEvents } from "../../js/data/calendar.js";

let uid = 0;

/**
 * Filter controls: what kind of listings (segmented radio), which room
 * (native select), and tag/kind (native select). Only rooms and tags with
 * active listings are offered, so closed rooms never show up as choices.
 * Fires nc-filter { scope, venueId, kind }.
 */
export function filterBar({ scope = "nights", venueId = "", kind = "", rooms = [], kinds = [] } = {}) {
  const id = ++uid;
  const form = h("form.nc-filters", { "aria-label": "Filter events", onsubmit: e => e.preventDefault() });
  const seg = h("fieldset.nc-segmented", {},
    h("legend.nc-label", {}, "Show"),
    h("div.nc-segmented__options", {}, Object.entries(SCOPES).map(([value, text]) =>
      h("label.nc-segmented__option", {},
        h("input", { type: "radio", name: `scope-${id}`, value, checked: value === scope }),
        h("span", {}, text)))),
  );
  const selectRoom = h("select.nc-select", { id: `nc-room-${id}`, name: "venue" },
    h("option", { value: "" }, "All rooms"),
    rooms.map(r => h("option", { value: r.id, selected: r.id === venueId }, r.name)),
  );
  const selectKind = h("select.nc-select", { id: `nc-kind-${id}`, name: "kind" },
    h("option", { value: "" }, "All tags"),
    kinds.map(k => h("option", { value: k.id, selected: k.id === kind }, k.label)),
  );

  form.append(
    seg,
    h("div.nc-filters__room", {}, h("label.nc-label", { for: `nc-room-${id}` }, "Room"), selectRoom),
    h("div.nc-filters__kind", {}, h("label.nc-label", { for: `nc-kind-${id}` }, "Tag"), selectKind),
  );

  form.addEventListener("change", () => {
    emit(form, "nc-filter", {
      scope: form.querySelector(`input[name="scope-${id}"]:checked`)?.value || "nights",
      venueId: selectRoom.value,
      kind: selectKind.value,
    });
  });
  return form;
}

export const meta = {
  name: "filter-bar",
  title: "Filter bar",
  summary: "Nights out vs everything, room, and tag/kind filters. Native radios and select, so keyboard and screen readers work without extra code. Emits nc-filter.",
  params: { scope: "nights | all", venue: "venue id", kind: "tag or kind id" },
};

export async function embed(params, ctx) {
  const model = await ctx.calendar();
  const scope = params.get("scope") || "nights";
  const venueId = params.get("venue") || "";
  const kind = params.get("kind") || params.get("tag") || "";
  const bar = filterBar({
    scope,
    venueId,
    kind,
    rooms: roomsWithEvents(model, { scope: "all" }),
    kinds: kindsWithEvents(model, { scope: "all" }),
  });
  bar.addEventListener("nc-filter", e => ctx.select("filter", "", e.detail));
  return bar;
}
