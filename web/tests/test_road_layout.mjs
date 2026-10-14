// Layout checks for the perspective road. These stay in node: no browser.
import { billboardScale } from "../components/event-card/event-card.js";
import { normalize } from "../js/data/calendar.js";
import {
  bandFrames,
  effectiveBodies,
  entryLabel,
  entryStroke,
  entryWeight,
  listingDates,
  lodFor,
  packSigns,
  perspective,
  posterFit,
  signScale,
  standAt,
  VENUE_COLORS,
  venuePaint,
  windowAt,
  listingInstant,
  timeDepth,
  timeLandmarks,
  timelinePlace,
} from "../road/layout.js";

const assert = (cond, msg) => { if (!cond) throw new Error(msg); };
const near = (a, b, eps, msg) => assert(Math.abs(a - b) < eps, `${msg}: ${a} vs ${b}`);

// Decision 005, plus a nudge that cannot send one vote to the ceiling.
assert(signScale(0, { dayTotal: 0, count: 1 }) === 1, "no votes stays at 1");
const one = signScale(1, { dayTotal: 1, count: 1 });
const fiveHundred = signScale(500, { dayTotal: 500, count: 1 });
assert(one > 1 && one < 1.2, `one vote grows a little, got ${one}`);
near(one, billboardScale(1), 0.02, "solo +1 stays on the billboard curve");
assert(fiveHundred > one, "500 going is larger than 1 going");
assert(signScale(10000, { dayTotal: 10000, count: 1 }) <= 1.75, "ceiling holds");
const shared = signScale(1, { dayTotal: 10, count: 5 });
assert(shared >= 1 && shared <= one + 0.001, "a shared +1 is not larger than a solo +1");

// On-screen size picks the level of detail. Base 4 used to force dots.
assert(lodFor(240, 400).lod === "full", "a tall near row is a billboard");
assert(lodFor(60, 140).lod === "title", "a mid row is a title");
assert(lodFor(30, 40).lod === "dot", "a short row is a dot");
const tiny = lodFor(8, 8);
assert(tiny.w > 0 && tiny.h > 0, "a tiny lane still has a size");

const g = perspective(1440, 1330);
const frames = bandFrames(g);
assert(frames.length >= 5, `expected several rows, got ${frames.length}`);
assert(frames.every(f => f.laneH > 0), "lane height stays positive");
assert(lodFor(frames[0].laneH, frames[0].laneW).lod === "full", `nearest row on a tall window is a billboard (${frames[0].laneH}px)`);
const laptop = bandFrames(perspective(1280, 860));
assert(laptop.length >= 4, `a laptop still has rows, got ${laptop.length}`);
assert(lodFor(laptop[0].laneH, laptop[0].laneW).lod === "full", `nearest row on a laptop is a billboard (${laptop[0].laneH}px)`);
const phone = bandFrames(perspective(390, 844));
assert(phone.length >= 3, `a phone still has rows, got ${phone.length}`);
assert(phone.every(f => f.laneH > 0), "phone lanes stay positive");
assert(lodFor(phone[0].laneH, phone[0].laneW).lod === "full", `nearest phone row is a billboard (${phone[0].laneH}px)`);
const docked = bandFrames(perspective(1440, 620, { ground: 620, horizon: 48 }));
assert(docked.length >= 4, `a road above the card still has rows, got ${docked.length}`);
assert(docked.every(f => f.laneH > 0), "docked lanes stay positive");
assert(lodFor(docked[0].laneH, docked[0].laneW).lod === "full", `nearest docked row is a billboard (${docked[0].laneH}px)`);
const street = bandFrames(perspective(1440, 900), 8);
assert(street.length === 8, `street-level keeps one row per night, got ${street.length}`);
const streetSpan = street[0].y + street[0].height - street[street.length - 1].y;
assert(streetSpan > 500, `street-level rows fill the road, span ${streetSpan}`);
assert(street[street.length - 1].y - perspective(1440, 900).horizonY < 40, "street-level rows reach the tip");
assert(lodFor(street[0].laneH, street[0].laneW).lod === "full", `nearest street-level row is a billboard (${street[0].laneH}px)`);
assert(perspective(1440, 900).k === perspective(1440, 900, {}).k, "omitting k keeps the default depth");
assert(perspective(1440, 900).horizonY === Math.round(900 * 0.32), "default horizon is street-level");
assert(perspective(1440, 900).groundY === 900, "default ground is the stage floor");

// Empty nights are not rows, and a later listing is reachable by moving the window.
const dates = listingDates([
  { date: "2026-10-13" },
  { date: "2026-10-16" },
  { date: "2026-11-25" },
], "2026-10-13");
assert(dates.join() === "2026-10-13,2026-10-16,2026-11-25", `gaps dropped, got ${dates}`);
const last = windowAt(dates, 2, 8);
assert(last.selected === "2026-11-25", "the far listing can stand in front");
assert(last.remaining === 0, "nothing is left past the last night");
const first = windowAt(dates, 0, 1);
assert(first.road[0] === "2026-10-16" && first.later && first.remaining === 1, "the first window leaves the rest for later");

const packed = packSigns(
  [{ w: 100, h: 40 }, { w: 100, h: 40 }, { w: 100, h: 40 }],
  120,
  50,
);
assert(packed.shown.length === 1 && packed.rest.length === 2, "overflow becomes the stack, one sign stays");
assert(packSigns([], 100, 40).shown.length === 0, "an empty lane packs nothing");
const overflow = packSigns([{ w: 20, h: 80 }], 40, 20);
assert(overflow.dot === true, "a sign taller than the lane collapses to a dot");

const stood = standAt(dates, 0, 2);
assert(stood.nights.join() === "2026-10-13,2026-10-16", `the night you stand in is the nearest row, got ${stood.nights}`);
assert(stood.remaining === 1, "one night stays past a two-row stand");
const farStand = standAt(dates, 2, 4);
assert(farStand.nights.join() === "2026-11-25", "standing on the last night leaves nothing further down the road");

const open = perspective(1440, 900, { ground: 900, horizon: 80 });
const narrow = perspective(1440, 900, { ground: 900, horizon: 80, road: 0.46 });
assert(narrow.Wb < open.Wb, "a smaller road fraction draws a narrower road");
assert(perspective(1440, 900).Wb === perspective(1440, 900, {}).Wb, "omitting the road fraction keeps the default");

assert(entryWeight({ free: true, price: "$40" }) === 1, "free stays the thin border");
assert(entryWeight({ price: 0 }) === 1, "zero dollars is free");
assert(entryWeight({ price: "" }) === 2, "a blank price is unlisted, not expensive");
assert(entryWeight({ price: null }) === 2, "a missing price is unlisted");
assert(entryWeight({ price: 10 }) === 3, "under $15");
assert(entryWeight({ price: "$20" }) === 5, "under $30");
assert(entryWeight({ price: 40 }) === 7, "under $50");
assert(entryWeight({ price: 80 }) === 9, "the rest is the thickest");
assert(entryLabel({ free: true, price: "" }) === "Free", "free is said as free");
assert(entryLabel({ price: "" }) === "Entry not listed", "no price is not invented");
assert(entryLabel({ price: 12 }) === "$12", "a whole dollar stays whole");
assert(entryLabel({ price: 12.5 }) === "$12.50", "cents are kept");
assert(entryStroke({ price: 80 }, 20) <= 2.4 + 0.001, "a small sign is not eaten by a thick border");
assert(entryStroke({ free: true }, 80) === 1, "a free sign keeps the hairline");

const ids = ["ross", "annie", "barrel"];
const paints = ids.map(id => venuePaint(id, ["barrel", "annie", "ross"]));
assert(new Set(paints.map(paint => paint.venue)).size === 3, "three venues get three colors");
assert(venuePaint("annie", ids).venue === venuePaint("annie", ["ross", "annie", "barrel"]).venue, "venue color follows the sorted id, not the list order");
assert(venuePaint("missing", ids).venue === "#6F6A5E", "an unknown venue is the neutral");
assert(paints.every(paint => paint.ink === "#121214" || paint.ink === "#F7F4EC"), "ink is one of the two readable choices");
assert(new Set(VENUE_COLORS).size === VENUE_COLORS.length, "every venue hue is unique");
assert(!VENUE_COLORS.some(hex => {
  const n = Number.parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const pink = r > 180 && b > 140 && g < r * 0.72 && g < b * 1.15;
  const cyan = b > 180 && g > 160 && r < Math.min(g, b) * 0.75;
  return pink || cyan;
}), "venue hues stay off pink and cyan");
assert(posterFit(900, 900) === "cover", "a square poster fills the bay");
assert(posterFit(1200, 800) === "cover", "a wide poster fills the bay");
assert(posterFit(800, 1200) === "contain", "a tall poster sits inside the bay");

assert(effectiveBodies({ bodies: 0 }, true) === 1, "a saved vote counts before the server does");
assert(effectiveBodies({ bodies: 4 }, true) === 4, "a saved vote does not add a second body");
assert(effectiveBodies({ bodies: 4 }, false) === 4, "server tally is kept");

const model = normalize({
  today: "2026-10-13",
  venues: [{ id: "v", name: "Room" }],
  events: [{
    id: "e",
    title: "Trivia",
    date: "2026-11-25",
    venueId: "v",
    kind: "trivia",
    categories: ["Free Events"],
    status: "EventCancelled",
    price: "",
    performers: [],
    checks: [],
  }],
});
const trivia = model.events.find(e => e.id === "e");
assert(trivia.title === "Trivia", "normalize keeps the title");

// --- continuous timeline ---
const noon = listingInstant({ date: "2026-10-17", minutes: 12 * 60 });
assert(noon.endsWith("12:00:00") || noon.includes("T12:00"), `noon default, got ${noon}`);
const stamped = listingInstant({ date: "2026-10-17", startsAt: "2026-10-17T19:30:00-07:00", minutes: 0 });
assert(stamped.includes("19:30") || Date.parse(stamped) === Date.parse("2026-10-17T19:30:00-07:00"), "startsAt wins");

const now = Date.parse("2026-10-17T18:00:00-07:00");
const dNear = timeDepth(Date.parse("2026-10-17T18:30:00-07:00"), now);
const dMid = timeDepth(Date.parse("2026-10-18T21:00:00-07:00"), now);
const dFar = timeDepth(Date.parse("2026-10-24T21:00:00-07:00"), now);
assert(dNear >= 0 && dMid > dNear && dFar > dMid, `near ${dNear} < mid ${dMid} < far ${dFar}`);
assert(dFar < 14.01, `far depth stays on the road curve, got ${dFar}`);
const dThree = timeDepth(Date.parse("2026-10-17T21:00:00-07:00"), now);
const nearRate = (dThree - dNear) / 2.5;
const farRate = (dFar - dMid) / (6 * 24);
assert(nearRate > 5 * farRate, `the next hours own the near road, near ${nearRate}/h vs far ${farRate}/h`);

const desk = perspective(1440, 900);
assert(Math.abs(desk.Wb / 1440 - 0.72) < 0.02, `wider desk road, Wb=${desk.Wb}`);
const gp = perspective(390, 844);
assert(Math.abs(gp.Wb / 390 - 0.64) < 0.03, `wider phone road, Wb=${gp.Wb}`);

const placed = timelinePlace([
  { id: "a", title: "A", date: "2026-10-17", startsAt: "2026-10-17T19:00:00-07:00", minutes: 19 * 60, bodies: 2 },
  { id: "b", title: "B", date: "2026-10-17", startsAt: "2026-10-17T19:05:00-07:00", minutes: 19 * 60 + 5, bodies: 5 },
  { id: "c", title: "C", date: "2026-10-18", startsAt: "2026-10-18T20:00:00-07:00", minutes: 20 * 60, bodies: 1 },
], { now, geom: desk, today: "2026-10-17" });
assert(placed.some(p => p.kind === "marker" && p.date === "2026-10-17"), "marker before first tonight show");
assert(placed.some(p => p.kind === "marker" && p.date === "2026-10-18"), "marker before next night");
const events = placed.filter(p => p.kind === "event");
assert(events[0].id === "a" || events[0].event.id === "a", "time order");
assert(events.length === 3, "three events");
const collide = events.filter(e => Math.abs((e.depth ?? e.d) - (events[0].depth ?? events[0].d)) < 0.05);
const xslot = timelinePlace([
  { id: "x", title: "X", date: "2026-10-17", startsAt: "2026-10-17T19:00:00-07:00", minutes: 1140, bodies: 1 },
  { id: "y", title: "Y", date: "2026-10-17", startsAt: "2026-10-17T19:00:00-07:00", minutes: 1140, bodies: 9 },
], { now, geom: desk, today: "2026-10-17", collideMinutes: 15 });
const xs = xslot.filter(p => p.kind === "event");
assert(xs.length === 2, "both same-minute shows kept");
assert(xs.some(p => (p.xNudge || 0) !== 0) || xs[0].x !== xs[1].x, "lateral nudge on collision");

const lone = timelinePlace([
  { id: "p", title: "P", date: "2026-10-17", startsAt: "2026-10-17T19:00:00-07:00", minutes: 1140 },
  { id: "q", title: "Q", date: "2026-10-17", startsAt: "2026-10-17T20:00:00-07:00", minutes: 1200 },
  { id: "r", title: "R", date: "2026-10-17", startsAt: "2026-10-17T21:00:00-07:00", minutes: 1260 },
], { now, geom: desk, today: "2026-10-17" }).filter(p => p.kind === "event");
assert(lone.every(p => p.xNudge !== 0 && p.lanes === 4), "lone signs take one of four lanes, never the centre line");
assert(Math.sign(lone[0].xNudge) !== Math.sign(lone[1].xNudge), "consecutive signs alternate sides");

const marks = timeLandmarks(now, Date.parse("2026-10-19T23:00:00-07:00"), desk, { minGap: 30, offsetMin: -420 });
assert(marks.length >= 3 && marks.length < 40, `a handful of clock landmarks, got ${marks.length}`);
assert(marks.every(m => new Date(m.ms).getUTCMinutes() === 0), "landmarks sit on whole hours");
assert(marks.every(m => ((new Date(m.ms).getUTCHours() - 7 + 24) % 3) === 0), "landmarks fall on local 3-hour steps");
assert(marks.every((m, i) => !i || (marks[i - 1].y - m.y >= 30 && m.ms > marks[i - 1].ms)), "landmarks recede and keep their spacing");

const farRoad = timelinePlace(Array.from({ length: 8 }, (_, i) => ({
  id: `f${i}`, title: `F${i}`, date: "2026-10-22", startsAt: `2026-10-22T${String(12 + i).padStart(2, "0")}:00:00-07:00`,
})), { now, geom: desk, today: "2026-10-17" }).filter(p => p.kind === "event");
assert(farRoad.every(p => p.lanes === 4), "far signs share the road four abreast");
assert(new Set(farRoad.map(p => p.xNudge)).size === 4, "far signs use all four lanes");

console.log("road layout checks passed");
