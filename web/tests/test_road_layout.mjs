// Layout checks for the perspective road. These stay in node: no browser.
import { billboardScale } from "../components/event-card/event-card.js";
import { eventIsFree, normalize } from "../js/data/calendar.js";
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

assert(eventIsFree({ categories: ["Arts & Exhibits", "Free Events"] }), "Free Events category counts");
assert(eventIsFree({ price: 0 }), "numeric zero is free");
assert(eventIsFree({ price: "Free" }), "the word Free is free");
assert(!eventIsFree({ price: "$15", categories: ["Music"] }), "a priced show is not free");

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
}, "test");
const trivia = model.events.find(e => e.id === "e");
assert(trivia.free === true, "normalize keeps free");
assert(trivia.cancelled === true, "normalize keeps cancelled");

console.log("road layout checks passed");
