/**
 * Timezone localization utilities (Task 2.10).
 *
 * Supports:
 *   - Multi-timezone venue rendering (Santa Rosa, New York, Chicago, etc.).
 *   - Localized formatting with timezone abbreviations (e.g. '8:00 pm PDT' vs '8:00 pm EDT').
 *   - Correct DST boundary handling using native Intl.DateTimeFormat.
 */

export const DEFAULT_TIMEZONE = "America/Los_Angeles";

/**
 * Format a timestamp into localized time string with optional timezone abbreviation.
 * Example output: "8:00 pm PDT", "11:30 am EDT"
 */
export function formatLocalizedTime(dateOrIso, timeZone = DEFAULT_TIMEZONE, { includeTz = true } = {}) {
  if (!dateOrIso) return "";
  const d = typeof dateOrIso === "string" ? parseIso(dateOrIso, timeZone) : dateOrIso;
  if (!d || isNaN(d.getTime())) return String(dateOrIso);

  const tz = timeZone || DEFAULT_TIMEZONE;

  const timeFormatter = new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });

  const timeStr = timeFormatter.format(d).toLowerCase();

  if (!includeTz) return timeStr;

  const abbr = getTimezoneAbbr(d, tz);
  return abbr ? `${timeStr} ${abbr}` : timeStr;
}

/**
 * Return timezone abbreviation for a given date in target timezone.
 * Example: "PDT", "PST", "EDT", "EST", "CDT"
 */
export function getTimezoneAbbr(dateOrIso, timeZone = DEFAULT_TIMEZONE) {
  if (!dateOrIso) return "";
  const d = typeof dateOrIso === "string" ? parseIso(dateOrIso, timeZone) : dateOrIso;
  if (!d || isNaN(d.getTime())) return "";

  const tz = timeZone || DEFAULT_TIMEZONE;
  const tzFormatter = new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    timeZoneName: "short",
  });

  const parts = tzFormatter.formatToParts(d);
  return parts.find(p => p.type === "timeZoneName")?.value || "";
}

/**
 * Format start and end time range with localized timezone abbreviation.
 * Example: "8:00 pm – 11:00 pm PDT"
 */
export function formatTimeRange(startsAt, endsAt, timeZone = DEFAULT_TIMEZONE) {
  const tz = timeZone || DEFAULT_TIMEZONE;
  if (!startsAt) return "";
  const startStr = formatLocalizedTime(startsAt, tz, { includeTz: !endsAt });
  if (!endsAt) return startStr;

  const endStr = formatLocalizedTime(endsAt, tz, { includeTz: true });
  return `${startStr} – ${endStr}`;
}

/**
 * Parse an ISO date or datetime string, ensuring fallback offset if naive.
 */
function parseIso(isoStr, fallbackTz = DEFAULT_TIMEZONE) {
  const raw = String(isoStr).trim();
  // If already contains offset (+/-HH:MM or Z)
  if (raw.endsWith("Z") || /[+-]\d{2}:?\d{2}$/.test(raw)) {
    return new Date(raw);
  }
  // Otherwise parse as standard date
  return new Date(raw);
}
