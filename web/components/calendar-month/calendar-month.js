import { h, emit } from "../../js/core/dom.js";
import { button } from "../button/button.js";
import { kindGlyph } from "../kind-tag/kind-tag.js";
import { monthScene } from "../../js/data/scene.js";
import { addDays, isValidDate, addMonths } from "../../js/data/dates.js";

let uid = 0;
const WEEKDAYS = [["Sun", "Sunday"], ["Mon", "Monday"], ["Tue", "Tuesday"], ["Wed", "Wednesday"], ["Thu", "Thursday"], ["Fri", "Friday"], ["Sat", "Saturday"]];
const chevron = dir => {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true"); s.setAttribute("fill", "none");
  s.setAttribute("stroke", "currentColor"); s.setAttribute("stroke-width", "2.5"); s.setAttribute("stroke-linecap", "round");
  s.innerHTML = dir < 0 ? '<path d="M15 5l-7 7 7 7"/>' : '<path d="M9 5l7 7-7 7"/>';
  return s;
};

/**
 * Month grid with date-picker keyboard support: one tab stop, arrows move a
 * day/week, Home/End go to the week's ends, PageUp/PageDown change month.
 * Wide containers show the first two titles in each cell.
 * Fires nc-select {kind:"day", date} and nc-shift {unit:"month", delta, focusDate}.
 */
export function calendarMonth(month, { focusDate, noun = "show", maxTitles = 2 } = {}) {
  const id = `nc-month-${++uid}`;
  const root = h("section.nc-month", { "aria-labelledby": id });
  const prev = button({ label: "Previous month", variant: "ghost", hideLabel: true, icon: chevron(-1) });
  const next = button({ label: "Next month", variant: "ghost", hideLabel: true, icon: chevron(1) });
  prev.addEventListener("click", () => emit(root, "nc-shift", { unit: "month", delta: -1 }));
  next.addEventListener("click", () => emit(root, "nc-shift", { unit: "month", delta: 1 }));

  const days = month.weeks.flat().filter(Boolean);
  const tabDate = [focusDate, ...days.filter(d => d.isSelected).map(d => d.date), ...days.filter(d => d.isToday).map(d => d.date), days[0]?.date]
    .find(d => d && days.some(x => x.date === d));

  const table = h("table.nc-month__grid", { role: "grid", "aria-labelledby": id },
    h("thead", {}, h("tr", {}, WEEKDAYS.map(([s, l]) => h("th", { scope: "col", abbr: l }, s)))),
    h("tbody", {}, month.weeks.map(week => h("tr", {}, week.map(day => {
      if (!day) return h("td.nc-month__pad", { "aria-hidden": "true" });
      const n = day.events.length;
      const btn = h("button.nc-month__day", {
        type: "button", "data-date": day.date, tabindex: day.date === tabDate ? "0" : "-1",
        "aria-label": `${day.long}${day.isToday ? ", today" : ""}, ${n ? `${n} ${noun}${n === 1 ? "" : "s"}` : `no ${noun}s`}`,
        "aria-pressed": String(!!day.isSelected), "aria-current": day.isToday ? "date" : null,
      },
        h("span.nc-month__num", { "aria-hidden": "true" }, String(day.day)),
        n ? h("span.nc-month__count", { "aria-hidden": "true" }, String(n)) : null,
        n ? h("ul.nc-month__titles", { role: "list", "aria-hidden": "true" },
          day.events.slice(0, maxTitles).map(e => h("li", {}, kindGlyph(e.kind), h("span", {}, e.title))),
          n > maxTitles ? h("li.nc-month__more", {}, `+${n - maxTitles}`) : null) : null,
      );
      return h("td", { role: "gridcell" }, btn);
    })))),
  );

  table.addEventListener("click", e => {
    const btn = e.target.closest(".nc-month__day");
    if (btn) emit(root, "nc-select", { kind: "day", date: btn.dataset.date });
  });
  table.addEventListener("keydown", e => {
    const btn = e.target.closest(".nc-month__day");
    if (!btn) return;
    const date = btn.dataset.date;
    const wd = new Date(`${date}T12:00:00Z`).getUTCDay();
    const step = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7, Home: -wd, End: 6 - wd }[e.key];
    let target = null;
    if (step != null) target = addDays(date, step);
    else if (e.key === "PageUp" || e.key === "PageDown") {
      const delta = e.key === "PageUp" ? -1 : 1;
      const key = addMonths(date.slice(0, 7), delta);
      const day = Math.min(Number(date.slice(8)), new Date(Date.UTC(+key.slice(0, 4), +key.slice(5, 7), 0)).getUTCDate());
      e.preventDefault();
      emit(root, "nc-shift", { unit: "month", delta, focusDate: `${key}-${String(day).padStart(2, "0")}` });
      return;
    } else return;
    e.preventDefault();
    const el = table.querySelector(`[data-date="${target}"]`);
    if (el) { moveTab(table, el); el.focus(); }
    else emit(root, "nc-shift", { unit: "month", delta: step < 0 ? -1 : 1, focusDate: target });
  });

  root.append(
    h("div.nc-month__nav", {}, prev, h("h2.nc-month__title", { id }, month.label), next),
    h("div.nc-month__scroll", {}, table),
  );
  return root;
}

function moveTab(table, el) {
  table.querySelectorAll('.nc-month__day[tabindex="0"]').forEach(b => b.setAttribute("tabindex", "-1"));
  el.setAttribute("tabindex", "0");
}

export const meta = {
  name: "calendar-month",
  title: "Calendar month",
  summary: "Month grid with date-picker keyboard support (arrows, Home/End, PageUp/PageDown). Counts on narrow screens, titles on wide.",
  params: { month: "YYYY-MM (defaults to this month)", date: "selected day", scope: "nights | all", venue: "venue id" },
};

export async function embed(params, ctx) {
  const model = await ctx.calendar();
  let date = isValidDate(params.get("date")) ? params.get("date") : model.today;
  let month = /^\d{4}-\d{2}$/.test(params.get("month") || "") ? params.get("month") : date.slice(0, 7);
  const scope = params.get("scope") || "nights";
  const venueId = params.get("venue") || "";
  const holder = h("div", {});
  const draw = focus => {
    holder.replaceChildren(calendarMonth(monthScene(model, { month, date, scope, venueId }), { focusDate: focus, noun: scope === "all" ? "listing" : "show" }));
    if (focus) holder.querySelector(`[data-date="${focus}"]`)?.focus();
  };
  holder.addEventListener("nc-shift", e => { month = addMonths(month, e.detail.delta); draw(e.detail.focusDate); });
  holder.addEventListener("nc-select", e => { if (e.detail.kind === "day") { date = e.detail.date; draw(date); } });
  draw();
  return holder;
}
