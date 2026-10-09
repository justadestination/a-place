import { h, emit } from "../../js/core/dom.js";
import { button } from "../button/button.js";
import { kindGlyph } from "../kind-tag/kind-tag.js";
import { weekScene } from "../../js/data/scene.js";
import { isValidDate } from "../../js/data/dates.js";

const chevron = dir => {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true"); s.setAttribute("fill", "none");
  s.setAttribute("stroke", "currentColor"); s.setAttribute("stroke-width", "2.5"); s.setAttribute("stroke-linecap", "round");
  s.innerHTML = dir < 0 ? '<path d="M15 5l-7 7 7 7"/>' : '<path d="M9 5l7 7-7 7"/>';
  return s;
};

/**
 * Seven days in a row. Every day shows how many events it has; on wide
 * containers it also shows the first titles, so names are visible at rest.
 *   week   weekScene() result
 * Fires nc-select {kind:"day", date} and nc-shift {unit:"week", delta}.
 */
export function calendarWeek(week, { noun = "show", maxTitles = 3 } = {}) {
  const root = h("section.nc-week", { "aria-label": `Week of ${week.label}` });
  const prev = button({ label: "Previous week", variant: "ghost", hideLabel: true, icon: chevron(-1) });
  const next = button({ label: "Next week", variant: "ghost", hideLabel: true, icon: chevron(1) });
  prev.addEventListener("click", () => emit(root, "nc-shift", { unit: "week", delta: -1 }));
  next.addEventListener("click", () => emit(root, "nc-shift", { unit: "week", delta: 1 }));
  root.append(
    h("div.nc-week__nav", {}, prev, h("p.nc-week__label", {}, week.label), next),
    h("ol.nc-week__days", { role: "list" }, week.days.map(day => {
      const n = day.events.length;
      const name = `${day.long}${day.isToday ? ", today" : ""}, ${n ? `${n} ${noun}${n === 1 ? "" : "s"}` : `no ${noun}s`}`;
      const titles = day.events.slice(0, maxTitles);
      const btn = h("button.nc-week__day", {
        type: "button", "data-date": day.date, "aria-label": name,
        "aria-pressed": String(!!day.isSelected), "aria-current": day.isToday ? "date" : null,
      },
        h("span.nc-week__weekday", { "aria-hidden": "true" }, day.weekdayShort),
        h("span.nc-week__num", { "aria-hidden": "true" }, String(day.day)),
        h("span.nc-week__count", { "aria-hidden": "true" }, n ? String(n) : "–"),
        n ? h("ul.nc-week__titles", { role: "list", "aria-hidden": "true" },
          titles.map(e => h("li", {}, kindGlyph(e.kind), h("span", {}, h("b", {}, e.start ? `${e.start} ` : ""), e.title))),
          n > titles.length ? h("li.nc-week__more", {}, `+${n - titles.length} more`) : null,
        ) : null,
      );
      btn.addEventListener("click", () => emit(btn, "nc-select", { kind: "day", date: day.date }));
      return h("li", {}, btn);
    })),
  );
  return root;
}

export const meta = {
  name: "calendar-week",
  title: "Calendar week",
  summary: "A seven-day strip. Counts on narrow screens, counts plus event titles on wide ones. Emits nc-select and nc-shift.",
  params: { date: "any day in the week (defaults to today)", scope: "nights | all", venue: "venue id" },
};

export async function embed(params, ctx) {
  const model = await ctx.calendar();
  let date = isValidDate(params.get("date")) ? params.get("date") : model.today;
  const scope = params.get("scope") || "nights";
  const venueId = params.get("venue") || "";
  const holder = h("div", {});
  const draw = () => holder.replaceChildren(calendarWeek(weekScene(model, { date, scope, venueId }), { noun: scope === "all" ? "listing" : "show" }));
  holder.addEventListener("nc-shift", e => {
    const d = new Date(`${date}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + 7 * e.detail.delta);
    date = d.toISOString().slice(0, 10); draw();
    holder.querySelector(`.nc-week__nav button:${e.detail.delta < 0 ? "first-child" : "last-child"}`)?.focus();
  });
  holder.addEventListener("nc-select", e => {
    if (e.detail.kind !== "day") return;
    date = e.detail.date; draw();
    holder.querySelector(`[data-date="${date}"]`)?.focus();
  });
  draw();
  return holder;
}
