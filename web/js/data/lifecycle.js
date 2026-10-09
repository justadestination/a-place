/**
 * Event Lifecycle Engine (Task 2.9).
 *
 * Provides:
 *   1. "Happening now" state calculation.
 *   2. Past events archive filtering.
 *   3. Recurring events expansion (weekly residencies) across multi-week horizons.
 */

const DEFAULT_DURATION_MS = 3 * 60 * 60 * 1000; // 3 hours

export function parseDate(val) {
  if (!val) return null;
  const d = new Date(val);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function computeLifecycle(startsAt, endsAt, now = new Date()) {
  const start = parseDate(startsAt);
  if (!start) {
    return {
      state: "upcoming",
      happeningNow: false,
      isPast: false,
      isArchived: false,
    };
  }

  const end = parseDate(endsAt) || new Date(start.getTime() + DEFAULT_DURATION_MS);
  const current = now instanceof Date ? now : new Date(now);

  if (current < start) {
    return {
      state: "upcoming",
      happeningNow: false,
      isPast: false,
      isArchived: false,
    };
  }

  if (current >= start && current <= end) {
    return {
      state: "happening_now",
      happeningNow: true,
      isPast: false,
      isArchived: false,
    };
  }

  return {
    state: "past",
    happeningNow: false,
    isPast: true,
    isArchived: true,
  };
}

export function expandRecurringEvents(events, startDateStr, endDateStr, now = new Date()) {
  const startD = new Date(`${startDateStr}T00:00:00`);
  const endD = new Date(`${endDateStr}T23:59:59`);

  const result = [];

  for (const ev of events) {
    const isRecurring = Boolean(ev.isRecurring || ev.is_recurring || ev.recurrence);
    if (!isRecurring) {
      if (!ev.date || (ev.date >= startDateStr && ev.date <= endDateStr)) {
        result.push(ev);
      }
      continue;
    }

    if (!ev.date) {
      result.push(ev);
      continue;
    }

    const baseD = new Date(`${ev.date}T00:00:00`);
    const baseStart = parseDate(ev.startsAt || ev.start);
    const baseEnd = parseDate(ev.endsAt || ev.end);

    // Weekly recurrence: advance by 7 days
    let curr = new Date(baseD);
    while (curr < startD) {
      curr.setDate(curr.getDate() + 7);
    }

    let occIndex = 0;
    while (curr <= endD) {
      occIndex++;
      const occDateStr = curr.toISOString().slice(0, 10);
      const isBase = (occDateStr === ev.date);
      const daysDiff = Math.round((curr - baseD) / (24 * 3600 * 1000));
      const msDiff = daysDiff * 24 * 3600 * 1000;

      const occStartsAt = baseStart ? new Date(baseStart.getTime() + msDiff).toISOString() : "";
      const occEndsAt = baseEnd ? new Date(baseEnd.getTime() + msDiff).toISOString() : "";

      const occ = {
        ...ev,
        id: isBase ? ev.id : `${ev.id}_occ_${occDateStr}`,
        date: occDateStr,
        isRecurring: true,
        baseEventId: ev.id,
        occurrenceIndex: occIndex,
        startsAt: occStartsAt || ev.startsAt,
        endsAt: occEndsAt || ev.endsAt,
      };

      const lc = computeLifecycle(occ.startsAt, occ.endsAt, now);
      occ.lifecycle = lc.state;
      occ.happeningNow = lc.happeningNow;
      occ.isPast = lc.isPast;
      occ.isArchived = lc.isArchived;

      result.push(occ);
      curr = new Date(curr);
      curr.setDate(curr.getDate() + 7);
    }
  }

  return result;
}

export function filterArchived(events, asOf = new Date()) {
  const active = [];
  const archived = [];
  for (const ev of events) {
    const lc = computeLifecycle(ev.startsAt, ev.endsAt, asOf);
    if (lc.isPast) {
      archived.push({ ...ev, ...lc });
    } else {
      active.push({ ...ev, ...lc });
    }
  }
  return { active, archived };
}
