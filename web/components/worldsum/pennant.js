/**
 * American Traditional pennant.
 *
 * Colors and charges follow the TacksForSnacks default flash: black ink,
 * crimson, burnt rust, gold, parchment. The dagger, the anchor, and the
 * acorn are the traditional marks from that studio. Cyber presets, the
 * Synapse homeserver, and the tackbot's room commands are not here.
 * The Steward says the lines.
 */

import { svg } from "../../js/core/dom.js";

const INK = "#0a080f";
const PARCHMENT = "#e8dcc4";
const GOLD = "#d49b00";
const CRIMSON = "#b8004f";
const CRIMSON_DEEP = "#7a0026";
const BROWN = "#5c3a1e";

export const FIELDS = [
  { id: "crimson", name: "Crimson", fill: CRIMSON },
  { id: "rust", name: "Burnt rust", fill: "#d04a00" },
  { id: "gold", name: "Gold", fill: GOLD },
  { id: "ink", name: "Ink", fill: "#14101d" },
  { id: "parchment", name: "Parchment", fill: PARCHMENT },
];

export const CHARGES = [
  { id: "dagger", name: "Dagger and rose" },
  { id: "anchor", name: "Anchor" },
  { id: "acorn", name: "Acorn" },
  { id: "rose", name: "Rose" },
  { id: "none", name: "Field only" },
];

const FIELD_LINE = {
  crimson: "Crimson. It reads from the trail.",
  rust: "Burnt rust. Heavy, and it holds.",
  gold: "Gold. Don't thin it out.",
  ink: "Ink field. The charge has to be the light.",
  parchment: "Parchment. The black line is the whole point.",
};

const CHARGE_LINE = {
  dagger: "Dagger and rose. That's a flag.",
  anchor: "Anchor. It holds. Don't hang a novel under it.",
  acorn: "Acorn. That's the mark. Keep it tight.",
  rose: "Just the rose. Crimson does the talking.",
  none: "No charge. Then the field has to be loud enough on its own.",
};

const CUT = {
  swallowtail: "M16 14 H80 L64 42 L80 70 H16 Z",
  notched: "M16 14 H80 L66 30 L80 42 L66 54 L80 70 H16 Z",
  banner: "M16 14 H78 V70 H16 Z",
};

const HOLDER_FLY = {
  human: "swallowtail",
  steward: "notched",
  business: "banner",
};

const FLIES = ["swallowtail", "notched", "banner"];

export function normalizeAppearance(raw) {
  const field = FIELDS.some((item) => item.id === raw?.field) ? raw.field : "parchment";
  const charge = CHARGES.some((item) => item.id === raw?.charge) ? raw.charge : "none";
  const motto = String(raw?.motto || "").replace(/\s+/g, " ").trim().slice(0, 24);
  const line = raw?.line === "fine" ? "fine" : "heavy";
  const ribbon = ribbonOn(raw);
  const fly = FLIES.includes(raw?.fly) ? raw.fly : "";
  return { field, charge, motto, line, ribbon, fly };
}

function ribbonOn(raw) {
  if (raw == null || raw.ribbon === undefined) return true;
  if (typeof raw.ribbon === "string") return ["1", "true", "yes", "on"].includes(raw.ribbon.trim().toLowerCase());
  return Boolean(raw.ribbon);
}

export function fieldById(id) {
  return FIELDS.find((item) => item.id === id) || FIELDS[0];
}

export function chargeById(id) {
  return CHARGES.find((item) => item.id === id) || CHARGES[CHARGES.length - 1];
}

export function stewardIntro() {
  return "One line is enough. Paint it black, or open every detail. An intent needs a sentence. It stays off the map until you list it. Keep it tight and keep it private.";
}

export function stewardOnField(id) {
  return FIELD_LINE[id] || FIELD_LINE.parchment;
}

export function stewardOnCharge(id) {
  return CHARGE_LINE[id] || CHARGE_LINE.none;
}

export function stewardNeedPlace() {
  return "Pick a place. I don't pin a flag to the whole forest.";
}

export function stewardOnList(placeName) {
  return `Listed at ${placeName}. That place is public now. You asked for it on the sheet.`;
}

export function stewardOnUpdate(placeName) {
  return `Updated. Still planted at ${placeName}. The ink is what people read.`;
}

export function stewardOnPull() {
  return "Pulled. The place is off the map. Keep it tight and keep it private.";
}

function chargeNodes(look) {
  const ink = look.field === "ink" ? PARCHMENT : INK;
  const light = look.field === "parchment" || look.field === "gold" ? INK : PARCHMENT;
  if (look.charge === "dagger") return chargeDagger(ink, light, look.field);
  if (look.charge === "anchor") return chargeAnchor(ink, look.field === "gold" ? BROWN : GOLD);
  if (look.charge === "acorn") return chargeAcorn(ink);
  if (look.charge === "rose") {
    const petal = look.field === "crimson" ? PARCHMENT : CRIMSON;
    const deep = look.field === "crimson" ? GOLD : CRIMSON_DEEP;
    return chargeRose(ink, petal, deep);
  }
  return [
    svg("line", { x1: 18, y1: 42, x2: 82, y2: 42, stroke: ink, "stroke-width": 8, "stroke-linecap": "round" }),
    svg("line", { x1: 30, y1: 58, x2: 70, y2: 58, stroke: ink, "stroke-width": 5, "stroke-linecap": "round" }),
  ];
}

function chargeRose(ink, petal, deep) {
  const spots = [[50, 34], [66, 48], [58, 66], [42, 66], [34, 48]];
  return [
    ...spots.map(([cx, cy]) => svg("circle", { cx, cy, r: 13, fill: petal, stroke: ink, "stroke-width": 2.2 })),
    svg("circle", { cx: 50, cy: 52, r: 8, fill: deep, stroke: ink, "stroke-width": 2 }),
  ];
}

function chargeDagger(ink, light, field) {
  const rose = field === "crimson" ? PARCHMENT : CRIMSON;
  const roseDeep = field === "crimson" ? GOLD : CRIMSON_DEEP;
  return [
    svg("g", { transform: "translate(14 22) scale(0.72)" }, chargeRose(ink, rose, roseDeep)),
    svg("path", { d: "M50 6 L58 34 L55 68 L50 82 L45 68 L42 34 Z", fill: light, stroke: ink, "stroke-width": 2.4 }),
    svg("path", { d: "M26 34 Q50 28 74 34 L70 42 Q50 38 30 42 Z", fill: GOLD, stroke: ink, "stroke-width": 2 }),
    svg("circle", { cx: 50, cy: 16, r: 4.5, fill: GOLD, stroke: ink, "stroke-width": 1.6 }),
  ];
}

function chargeAnchor(ink, metal) {
  return [
    svg("circle", { cx: 50, cy: 16, r: 7, fill: "none", stroke: metal, "stroke-width": 3.5 }),
    svg("line", { x1: 28, y1: 30, x2: 72, y2: 30, stroke: metal, "stroke-width": 5, "stroke-linecap": "round" }),
    svg("line", { x1: 50, y1: 22, x2: 50, y2: 76, stroke: ink, "stroke-width": 5, "stroke-linecap": "round" }),
    svg("path", { d: "M22 58 Q50 94 78 58", fill: "none", stroke: ink, "stroke-width": 5.5, "stroke-linecap": "round" }),
    svg("polygon", { points: "22,58 14,46 34,52", fill: metal, stroke: ink, "stroke-width": 1.5 }),
    svg("polygon", { points: "78,58 86,46 66,52", fill: metal, stroke: ink, "stroke-width": 1.5 }),
  ];
}

function chargeAcorn(ink) {
  return [
    svg("path", { d: "M30 44 Q50 18 70 44 L66 50 Q50 38 34 50 Z", fill: GOLD, stroke: ink, "stroke-width": 2.4 }),
    svg("circle", { cx: 50, cy: 20, r: 4, fill: GOLD, stroke: ink, "stroke-width": 1.6 }),
    svg("path", { d: "M34 48 Q32 70 50 84 Q68 70 66 48 Z", fill: BROWN, stroke: ink, "stroke-width": 2.4 }),
    svg("line", { x1: 50, y1: 52, x2: 50, y2: 76, stroke: PARCHMENT, "stroke-width": 1.6 }),
  ];
}

export function pennantSvg(appearance, holder = "human", options = {}) {
  const look = normalizeAppearance(appearance);
  const cloth = fieldById(look.field).fill;
  const fly = CUT[look.fly] || CUT[HOLDER_FLY[holder]] || CUT.swallowtail;
  const fine = look.line === "fine";
  const cls = options.preview
    ? "nc-worldsum__pennant nc-worldsum__pennant--preview"
    : "nc-worldsum__pennant";
  const parts = [
    svg("line", { x1: 10, y1: 8, x2: 10, y2: 104, stroke: INK, "stroke-width": fine ? 1.5 : 3.5, "stroke-linecap": "round" }),
    svg("circle", { cx: 10, cy: 8, r: 4, fill: GOLD, stroke: INK, "stroke-width": 1.5 }),
    svg("path", { d: fly, fill: cloth, stroke: INK, "stroke-width": fine ? 1.5 : 3, "stroke-linejoin": "round" }),
  ];
  if (look.ribbon) parts.push(svg("path", { d: "M16 76 H82 L76 96 H22 Z", fill: INK }));
  parts.push(svg("g", { transform: "translate(22 14) scale(0.5)" }, chargeNodes(look)));
  return svg("svg", {
    class: cls,
    viewBox: "0 0 96 110",
    role: "img",
    "aria-hidden": "true",
    "data-field": look.field,
    "data-charge": look.charge,
    "data-motto": look.motto,
    "data-line": look.line,
    "data-ribbon": look.ribbon ? "true" : "false",
    "data-fly": look.fly,
  }, parts);
}

const PLACE_ALIASES = [
  ["courthouse square", "square"],
  ["railroad square", "rail"],
  ["dark pool", "dark-pool"],
  ["north gate", "north-gate"],
  ["far lake", "far-lake"],
  ["long water", "long-water"],
  ["three pools", "three-pools"],
  ["east water", "east-water"],
  ["the narrows", "narrows"],
  ["narrows", "narrows"],
  ["the lot", "lot"],
  ["the square", "square"],
  ["the rail", "rail"],
];

const PLACE_NAMES = {
  square: "Courthouse Square",
  rail: "Railroad Square",
  "dark-pool": "Dark Pool",
  lot: "The Lot",
  "north-gate": "North Gate",
  "far-lake": "Far Lake",
  "long-water": "Long Water",
  narrows: "The Narrows",
  "three-pools": "Three Pools",
  "east-water": "East Water",
};

const COLOR_WORDS = [
  ["rust", ["burnt rust", "rust", "orange"], "Burnt rust. Heavy, and it holds."],
  ["crimson", ["crimson", "red"], "Crimson. It reads from the trail."],
  ["parchment", ["parchment", "paper"], "Parchment. The black line is the whole point."],
  ["ink", ["black", "ink"], "Painted black."],
  ["gold", ["gold"], "Gold. Don't thin it out."],
];

const CHARGE_WORDS = [
  ["dagger", ["dagger and rose", "dagger"], "Dagger and rose. That's a flag."],
  ["anchor", ["anchor"], "Anchor. It holds."],
  ["acorn", ["acorn"], "Acorn. That's the mark."],
  ["rose", ["rose"], "Just the rose."],
  ["none", ["no charge", "field only", "plain", "bare"], "No charge. The field has to carry it."],
];

function hasWord(text, phrase) {
  const escaped = phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(?<![a-z0-9])${escaped}(?![a-z0-9])`).test(text);
}

// A part made only of these words is a flash order, even inside a longer
// sentence ("selling an amp and crimson"). "red wine" is not: "wine" isn't here.
// Keep in step with _FLASH_WORDS and _COMMAND in shadenet/serendipilyst/flash.py.
const FLASH_WORDS = new Set((
  "a an the it its with no on off at in to field line fly ribbon charge only "
  + "crimson red rust burnt orange gold ink black parchment paper "
  + "dagger rose anchor acorn plain bare "
  + "fine thin heavy thick bold swallowtail swallow tail notched notch banner "
  + "courthouse railroad square rail dark pool lot north gate far lake long water narrows three pools east "
  + "list unlist pull"
).split(" "));
const COMMAND = /^(?:motto\b|list\b|unlist\b|pull\b|paint\b|make it\b|hang it\b|plant it\b|put it\b|take it\b|no ribbon\b|ribbon\b)/i;
const MOTTO = /^motto\s*[:\-]?\s*(.+)$/i;

function orderParts(text) {
  const pieces = text.replace(/dagger and rose/gi, "dagger_and_rose").split(/(\s*,\s*|\s+and\s+|(?<=[.!?])\s+)/i);
  const out = [];
  let sep = "";
  pieces.forEach((piece, index) => {
    if (index % 2) {
      sep = piece;
      return;
    }
    const part = piece.replace(/dagger_and_rose/gi, "dagger and rose").trim();
    if (part) out.push([sep, part]);
    sep = "";
  });
  return out;
}

function isOrder(part) {
  const low = part.toLowerCase().trim();
  if (COMMAND.test(low)) return true;
  const words = low.match(/[a-z]+/g) || [];
  return words.length > 0 && words.every((word) => FLASH_WORDS.has(word));
}

function opensSentence(part) {
  if (MOTTO.test(part.trim())) return true;
  try {
    return profileClause(part) !== null;
  } catch {
    return false;
  }
}

function spokenClauses(text) {
  const parts = orderParts(text);
  const merged = [];
  let index = 0;
  while (index < parts.length) {
    let clause = parts[index][1];
    index += 1;
    if (opensSentence(clause)) {
      while (index < parts.length && !".!?".includes(clause[clause.length - 1])
        && !isOrder(parts[index][1]) && !opensSentence(parts[index][1])) {
        clause = `${clause}${parts[index][0]}${parts[index][1]}`;
        index += 1;
      }
    }
    merged.push(clause);
  }
  return merged;
}

function colorIn(clause) {
  let found = null;
  for (const [field, phrases, line] of COLOR_WORDS) {
    for (const phrase of phrases) {
      if (hasWord(clause, phrase)) {
        if (found && found[0] !== field) throw new Error("one field at a time");
        found = [field, line];
        break;
      }
    }
  }
  return found;
}

function chargeIn(clause) {
  for (const [charge, phrases, line] of CHARGE_WORDS) {
    if (phrases.some((phrase) => hasWord(clause, phrase))) return [charge, line];
  }
  return null;
}

function placeIn(clause) {
  for (const [phrase, placeId] of PLACE_ALIASES) {
    if (hasWord(clause, phrase)) return placeId;
  }
  return null;
}

const INTENT_LINES = {
  conversation: "Conversation.",
  work: "Work.",
  fun: "Fun.",
  sale: "For sale.",
  purchase: "Looking to purchase.",
};

const CLEARS = {
  conversation: ["not looking for a conversation", "drop the conversation"],
  work: ["not available to work", "drop the work"],
  fun: ["not looking for fun", "drop the fun"],
  sale: ["nothing for sale", "drop the sale"],
  purchase: ["not looking to purchase", "not looking to buy", "drop the purchase"],
};

const ATTEMPT = /^(?:i am |i'm |i have )?(?:looking for a conversation|conversation|available (?:to|for) work|looking for fun|(?:stuff|something) for sale|for sale|selling|looking to (?:purchase|buy)|good at|i enjoy|enjoy|i (?:don't|do not|won't|wont) want|not part of|i refuse)\b/i;
// A dot between two digits is a decimal point, not the end of a sentence.
const STOP = /(?<!\d)[.!?]|[.!?](?!\d)/g;

function oneSentence(value, what = "an intent") {
  const text = String(value || "").trim().replace(/^["']|["']$/g, "").replace(/\s+/g, " ");
  if (!text) throw new Error(`${what} needs a sentence`);
  if (text.length > 160) throw new Error("that sentence is longer than 160 characters");
  const stops = [...text.matchAll(STOP)].map((match) => match.index);
  if (stops.length > 1 || (stops.length && stops[stops.length - 1] !== text.length - 1)) {
    throw new Error("one sentence");
  }
  return text;
}

function profileClause(clause) {
  const raw = clause.trim();
  const low = raw.toLowerCase();
  for (const [kind, phrases] of Object.entries(CLEARS)) {
    if (phrases.includes(low)) {
      return { field: "intent", kind, sentence: "", reply: `${INTENT_LINES[kind]} Off the flag.` };
    }
  }
  const profiles = [
    ["good_at", /^(?:i am |i'm )?good at\s+(.+)$/i, "Good at"],
    ["enjoy", /^(?:i enjoy|enjoy)\s+(.+)$/i, "You enjoy"],
    ["refuse", /^(?:i (?:don't|do not|won't|wont) want(?: to be a part of)?|not part of|i refuse)\s+(.+)$/i, "You won't be part of"],
  ];
  for (const [field, pattern, lead] of profiles) {
    const match = raw.match(pattern);
    if (!match) continue;
    const text = oneSentence(match[1], "that line");
    return { field, kind: "", sentence: text, reply: `${lead} ${text}.` };
  }
  const intents = [
    ["conversation", /^(?:i am |i'm )?looking for a conversation(?: about| on|:)?\s+(.+)$/i],
    ["conversation", /^conversation(?: about|:)\s+(.+)$/i],
    ["work", /^(?:i am |i'm )?available (?:to|for) work(?:[:,]| on| for)?\s+(.+)$/i],
    ["fun", /^(?:i am |i'm )?looking for fun(?:[:,]| about)?\s+(.+)$/i],
    ["sale", /^(?:i have )?(?:stuff|something) for sale[:,]?\s+(.+)$/i],
    ["sale", /^(?:for sale|selling)[:,]?\s+(.+)$/i],
    ["purchase", /^(?:i am |i'm )?looking to (?:purchase|buy)\s+(.+)$/i],
  ];
  for (const [kind, pattern] of intents) {
    const match = raw.match(pattern);
    if (!match) continue;
    const text = oneSentence(match[1]);
    return { field: "intent", kind, sentence: text, reply: `${INTENT_LINES[kind]} ${text}` };
  }
  if (ATTEMPT.test(low)) throw new Error("an intent needs a sentence");
  return null;
}

function applyClause(clause, look, effect, notes) {
  const motto = clause.trim().match(MOTTO);
  if (motto) {
    const text = motto[1].trim().replace(/^["']|["']$/g, "");
    if (text.length > 24) throw new Error("motto is longer than 24 characters");
    look.motto = text;
    notes.push(`Motto ${text}.`);
    return true;
  }
  const profile = profileClause(clause);
  if (profile) {
    const bucket = effect.profile || (effect.profile = { intents: [], good_at: null, enjoy: null, refuse: null });
    if (profile.field === "intent") {
      if (bucket.intents.some((item) => item.kind === profile.kind)) throw new Error("one mark per intent");
      bucket.intents.push({ kind: profile.kind, sentence: profile.sentence });
    } else bucket[profile.field] = profile.sentence;
    notes.push(profile.reply);
    return true;
  }
  const low = clause.toLowerCase();
  let hit = false;
  const color = colorIn(low);
  if (color) {
    look.field = color[0];
    notes.push(color[1]);
    hit = true;
  }
  const charge = chargeIn(low);
  if (charge) {
    look.charge = charge[0];
    notes.push(charge[1]);
    hit = true;
  }
  if (hasWord(low, "fine") || hasWord(low, "thin")) {
    look.line = "fine";
    notes.push("Fine line.");
    hit = true;
  } else if (hasWord(low, "heavy") || hasWord(low, "thick") || hasWord(low, "bold")) {
    look.line = "heavy";
    notes.push("Heavy line.");
    hit = true;
  }
  if (["no ribbon", "ribbon off", "without a ribbon", "without the ribbon"].some((phrase) => hasWord(low, phrase))) {
    look.ribbon = false;
    notes.push("Ribbon off.");
    hit = true;
  } else if (hasWord(low, "ribbon")) {
    look.ribbon = true;
    notes.push("Ribbon on.");
    hit = true;
  }
  const place = placeIn(low);
  if (hasWord(low, "swallowtail") || hasWord(low, "swallow tail")) {
    look.fly = "swallowtail";
    notes.push("Swallowtail.");
    hit = true;
  } else if (hasWord(low, "notched") || hasWord(low, "notch")) {
    look.fly = "notched";
    notes.push("Notched.");
    hit = true;
  } else if (hasWord(low, "banner")) {
    look.fly = "banner";
    notes.push("Banner.");
    hit = true;
  }
  if (place) {
    effect.placeId = place;
    hit = true;
  }
  const pull = ["pull it", "pull the", "take it down", "take it off", "unlist"].some((phrase) => hasWord(low, phrase));
  const listing = low === "list" || low.startsWith("list ") || ["list it", "list this", "plant it", "hang it", "put it up", "put it on"].some((phrase) => hasWord(low, phrase));
  if (pull && listing) throw new Error("list it or pull it, not both");
  if (pull) {
    effect.listed = false;
    notes.push("Pulled. The place is off the map.");
    hit = true;
  } else if (listing) {
    effect.listed = true;
    const where = PLACE_NAMES[effect.placeId] || "";
    notes.push(where ? `Listed at ${where}.` : "Listed.");
    hit = true;
  } else if (place) {
    notes.push(`${PLACE_NAMES[place]}. Still off the map until you list it.`);
  }
  return hit;
}

export function hearOrder(text, appearance) {
  const said = String(text || "").trim();
  if (!said) throw new Error("tell the Steward what to paint");
  if (said.length > 200) throw new Error("that order is longer than 200 characters");
  const base = appearance || {};
  const look = {
    field: String(base.field || "parchment").trim().toLowerCase(),
    charge: String(base.charge || "none").trim().toLowerCase(),
    motto: String(base.motto || "").trim(),
    line: String(base.line || "heavy").trim().toLowerCase(),
    ribbon: base.ribbon === undefined ? true : ribbonOn(base),
    fly: String(base.fly || "").trim().toLowerCase(),
  };
  const effect = { listed: null, placeId: null };
  const notes = [];
  for (const clause of spokenClauses(said)) {
    if (!applyClause(clause, look, effect, notes)) {
      throw new Error("tell the Steward a field, a charge, a motto, or paint it black");
    }
  }
  return {
    appearance: {
      field: look.field,
      charge: look.charge,
      motto: look.motto,
      line: look.line === "fine" ? "fine" : "heavy",
      ribbon: look.ribbon !== false,
      fly: FLIES.includes(look.fly) ? look.fly : "",
    },
    listed: effect.listed,
    placeId: effect.placeId,
    reply: notes.join(" "),
    profile: effect.profile || null,
  };
}

function iconFrame(children) {
  return svg("svg", {
    class: "nc-worldsum__intent-icon",
    viewBox: "0 0 32 32",
    "aria-hidden": "true",
  }, children);
}

export function intentIcon(kind) {
  if (kind === "conversation") {
    return iconFrame([
      svg("path", { d: "M6 7 H26 V20 H18 L12 27 V20 H6 Z", fill: PARCHMENT, stroke: INK, "stroke-width": "2", "stroke-linejoin": "round" }),
      svg("path", { d: "M10 12 H22 M10 16 H18", fill: "none", stroke: INK, "stroke-width": "1.6", "stroke-linecap": "round" }),
    ]);
  }
  if (kind === "work") {
    return iconFrame([
      svg("rect", { x: "5", y: "13", width: "14", height: "7", fill: INK }),
      svg("rect", { x: "14", y: "7", width: "13", height: "6", fill: BROWN, stroke: INK, "stroke-width": "1.6" }),
      svg("rect", { x: "18", y: "13", width: "3", height: "14", fill: BROWN, stroke: INK, "stroke-width": "1.4" }),
    ]);
  }
  if (kind === "fun") {
    return iconFrame([
      svg("polygon", {
        points: "16,3 19.6,12 29,12 21.4,17.6 24.2,27 16,21.6 7.8,27 10.6,17.6 3,12 12.4,12",
        fill: GOLD,
        stroke: INK,
        "stroke-width": "1.6",
        "stroke-linejoin": "round",
      }),
    ]);
  }
  if (kind === "sale") {
    return iconFrame([
      svg("path", { d: "M13 5 H25 L28 9 V27 H9 V14 Z", fill: CRIMSON, stroke: INK, "stroke-width": "2", "stroke-linejoin": "round" }),
      svg("circle", { cx: "15", cy: "11", r: "1.6", fill: PARCHMENT }),
    ]);
  }
  return iconFrame([
    svg("path", {
      d: "M7 16 V11 H11 V16 M11 14 V8 H15 V16 M15 13 V7 H19 V17 M19 14 V10 H23 V20 C23 25 19 28 15 28 H11 C8 28 6 24 6 20 V16 Z",
      fill: PARCHMENT,
      stroke: INK,
      "stroke-width": "1.6",
      "stroke-linejoin": "round",
    }),
  ]);
}

export function heartMark() {
  return svg("svg", {
    class: "nc-worldsum__rate-icon",
    viewBox: "0 0 32 32",
    "aria-hidden": "true",
  }, svg("path", {
    d: "M16 27 C6 18 4 12 8 8 C11 5 15 7 16 11 C17 7 21 5 24 8 C28 12 26 18 16 27 Z",
    fill: CRIMSON,
    stroke: INK,
    "stroke-width": "1.6",
    "stroke-linejoin": "round",
  }));
}

export function flameMark() {
  return svg("svg", {
    class: "nc-worldsum__rate-icon",
    viewBox: "0 0 32 32",
    "aria-hidden": "true",
  }, [
    svg("path", {
      d: "M16 3 C18 10 26 12 26 20 C26 26 21 29 16 29 C11 29 6 26 6 20 C6 14 12 13 11 8 C14 12 15 12 16 3 Z",
      fill: "#d04a00",
      stroke: INK,
      "stroke-width": "1.6",
      "stroke-linejoin": "round",
    }),
    svg("path", {
      d: "M16 16 C17 19 21 20 21 24 C21 27 18 28 16 28 C13 28 11 26 11 23 C11 20 14 19 16 16 Z",
      fill: GOLD,
      stroke: INK,
      "stroke-width": "1.2",
    }),
  ]);
}
