// Date-only helpers. Dates are "YYYY-MM-DD" strings in America/Los_Angeles,
// the calendar's home zone. Arithmetic runs in UTC so DST never shifts a day.

export const ZONE = "America/Los_Angeles";

export function today(now = new Date()) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: ZONE, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}

const asUTC = iso => new Date(`${iso}T12:00:00Z`);
const fmt = (opts) => new Intl.DateTimeFormat("en-US", { timeZone: "UTC", ...opts });
const F = {
  weekday: fmt({ weekday: "long" }),
  weekdayShort: fmt({ weekday: "short" }),
  month: fmt({ month: "long" }),
  monthShort: fmt({ month: "short" }),
  monthYear: fmt({ month: "long", year: "numeric" }),
  long: fmt({ weekday: "long", month: "long", day: "numeric" }),
  medium: fmt({ weekday: "short", month: "short", day: "numeric" }),
};

export function addDays(iso, n) {
  const d = asUTC(iso);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export function addMonths(monthKey, n) {
  const [y, m] = monthKey.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 + n, 1));
  return d.toISOString().slice(0, 7);
}

/** Sunday that starts the week containing iso (US calendars start on Sunday). */
export function weekStart(iso) { return addDays(iso, -asUTC(iso).getUTCDay()); }

export function dayOfMonth(iso) { return Number(iso.slice(8, 10)); }
export function monthKey(iso) { return iso.slice(0, 7); }
export function daysInMonth(key) { const [y, m] = key.split("-").map(Number); return new Date(Date.UTC(y, m, 0)).getUTCDate(); }
export function weekdayIndex(iso) { return asUTC(iso).getUTCDay(); }

export const label = {
  weekday: iso => F.weekday.format(asUTC(iso)),
  weekdayShort: iso => F.weekdayShort.format(asUTC(iso)),
  monthShort: iso => F.monthShort.format(asUTC(iso)),
  monthYear: key => F.monthYear.format(asUTC(`${key}-01`)),
  long: iso => F.long.format(asUTC(iso)),
  medium: iso => F.medium.format(asUTC(iso)),
};

/** "Tonight", "Tomorrow", or "Friday, October 9". */
export function relative(iso, now = today()) {
  if (iso === now) return "Tonight";
  if (iso === addDays(now, 1)) return "Tomorrow";
  return label.long(iso);
}

export function isValidDate(iso) { return /^\d{4}-\d{2}-\d{2}$/.test(iso || "") && !Number.isNaN(asUTC(iso).getTime()); }
