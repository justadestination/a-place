// Scene models: renderer-neutral views of the data. The DOM components and the
// 3D renderer both draw from these, so a week in 2D and a week in AR are the
// same object with the same ids, labels and order. See docs/ARCHITECTURE_2D_3D.md.

import { addDays, weekStart, label, dayOfMonth, daysInMonth, weekdayIndex, monthKey } from "./dates.js";
import { filterEvents, byDate } from "./calendar.js";

function dayNode(iso, events, todayIso, selected) {
  return {
    date: iso,
    weekday: label.weekday(iso), weekdayShort: label.weekdayShort(iso),
    day: dayOfMonth(iso), month: label.monthShort(iso),
    long: label.long(iso),
    isToday: iso === todayIso, isSelected: iso === selected,
    events: events || [],
  };
}

/** Seven days starting the Sunday of the week containing `date`. */
export function weekScene(model, { date, scope = "nights", venueId = "" } = {}) {
  const start = weekStart(date || model.today);
  const index = byDate(filterEvents(model, { scope, venueId }));
  const days = Array.from({ length: 7 }, (_, i) => {
    const iso = addDays(start, i);
    return dayNode(iso, index.get(iso), model.today, date);
  });
  return { kind: "week", start, end: addDays(start, 6), days, label: `${label.medium(start)} – ${label.medium(addDays(start, 6))}` };
}

/** One day's agenda. */
export function dayScene(model, { date, scope = "nights", venueId = "" } = {}) {
  const iso = date || model.today;
  const events = filterEvents(model, { scope, venueId }).filter(e => e.date === iso);
  return dayNode(iso, events, model.today, iso);
}

/** A month as weeks of 7 cells (null = padding outside the month). */
export function monthScene(model, { month, date, scope = "nights", venueId = "" } = {}) {
  const key = month || monthKey(date || model.today);
  const index = byDate(filterEvents(model, { scope, venueId }));
  const first = `${key}-01`;
  const lead = weekdayIndex(first);
  const cells = Array(lead).fill(null);
  for (let d = 1; d <= daysInMonth(key); d++) {
    const iso = `${key}-${String(d).padStart(2, "0")}`;
    cells.push(dayNode(iso, index.get(iso), model.today, date));
  }
  while (cells.length % 7) cells.push(null);
  const weeks = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
  return { kind: "month", month: key, label: label.monthYear(key), weeks };
}
