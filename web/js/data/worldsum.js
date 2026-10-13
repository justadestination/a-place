/**
 * WorldSum — a Nuuksio forest sheet pinned to two Santa Rosa milestones.
 *
 * Water centers are from Nominatim (OpenStreetMap), October 2026:
 *   Haukkalampi, Haltia, Mustalampi, the Haukkalampi lot, Kattila,
 *   Iso Majaslampi, Ruuhijärvi, Nuuksion Pitkäjärvi, Kolmoislampi, Urja.
 * A similarity transform pins Haukkalampi to Old Courthouse Square and
 * Haltia to Railroad Square. That lands the sheet at −117°. The page
 * then spins the sheet two full turns onto that bearing.
 *
 * Finnish names are replaced with plain ones. WorldSum is the country
 * name for the sheet. No WorldSum file was in the tree to copy from.
 */

export const VIEW = { width: 1000, height: 720 };

export const ANCHORS = [
  {
    id: "square",
    name: "Courthouse Square",
    from: "Haukkalampi, Nuuksio",
    x: 590.6,
    y: 127.7,
  },
  {
    id: "rail",
    name: "Railroad Square",
    from: "Haltia, Espoo",
    x: 294.4,
    y: 287.7,
  },
];

export const PLACES = [
  { id: "square", name: "Courthouse Square", x: 590.6, y: 127.7, water: true, r: 28 },
  { id: "rail", name: "Railroad Square", x: 294.4, y: 287.7, water: false, r: 0 },
  { id: "dark-pool", name: "Dark Pool", x: 543, y: 93.7, water: true, r: 18 },
  { id: "lot", name: "The Lot", x: 569.9, y: 175.6, water: false, r: 0 },
  { id: "north-gate", name: "North Gate", x: 920, y: 216.3, water: false, r: 0 },
  { id: "far-lake", name: "Far Lake", x: 464.6, y: 640, water: true, r: 34 },
  { id: "long-water", name: "Long Water", x: 467.2, y: 477.9, water: true, r: 26 },
  { id: "narrows", name: "The Narrows", x: 80, y: 303.9, water: true, r: 40 },
  { id: "three-pools", name: "Three Pools", x: 357.6, y: 80, water: true, r: 16 },
  { id: "east-water", name: "East Water", x: 269.5, y: 601.8, water: true, r: 22 },
];

export const TRAILS = [
  ["square", "dark-pool"],
  ["square", "lot"],
  ["square", "three-pools"],
  ["lot", "rail"],
  ["rail", "long-water"],
  ["long-water", "far-lake"],
  ["long-water", "east-water"],
  ["rail", "narrows"],
  ["square", "north-gate"],
];

/**
 * People and flags standing on the sheet. `you` is the reader.
 * Marks are set near a place, not on its exact center, so the pennants
 * can be told apart. Near/far still uses these points.
 * A flag is on the sheet only when `listed` is true. `placeId` matches
 * PLACES. The flash is field, charge, and motto.
 */
export const PEOPLE = [
  {
    id: "you",
    name: "You",
    kind: "you",
    bored: true,
    listed: false,
    placeId: "",
    x: 555,
    y: 170,
    side: "s",
    note: "Not listed. This dot is only on your screen.",
  },
  {
    id: "lumen",
    name: "Lumen",
    kind: "human",
    bored: true,
    listed: true,
    placeId: "square",
    appearance: { field: "crimson", charge: "dagger", motto: "TUBE AMP" },
    x: 640,
    y: 88,
    side: "e",
    intents: [{ kind: "conversation", sentence: "A tube amp that still has the hum in it." }],
    note: "Human flag at Courthouse Square. Looking for a conversation about a tube amp.",
  },
  {
    id: "door-steward",
    name: "Door Steward",
    kind: "steward",
    bored: false,
    listed: true,
    placeId: "square",
    appearance: { field: "gold", charge: "acorn", motto: "DOOR" },
    x: 790,
    y: 340,
    side: "s",
    linkedTo: "lumen",
    note: "Steward flag for Lumen. Holds the calendar and the inbox.",
  },
  {
    id: "jules",
    name: "Jules",
    kind: "person",
    bored: true,
    x: 620,
    y: 248,
    side: "s",
    intents: [{ kind: "work", sentence: "Available to load in." }],
    note: "Available to load in.",
  },
  {
    id: "mara",
    name: "Mara",
    kind: "person",
    bored: true,
    x: 470,
    y: 55,
    side: "w",
    note: "Bored at Dark Pool.",
  },
  {
    id: "pia",
    name: "Pia",
    kind: "person",
    bored: true,
    x: 380,
    y: 340,
    side: "e",
    note: "Bored at Railroad Square, too far to hear you.",
  },
  {
    id: "otto",
    name: "Otto",
    kind: "person",
    bored: true,
    x: 520,
    y: 500,
    side: "e",
    note: "Bored at Long Water.",
  },
  {
    id: "nils",
    name: "Nils",
    kind: "person",
    bored: false,
    x: 860,
    y: 260,
    side: "s",
    note: "At North Gate, already in the middle of something.",
  },
  {
    id: "foundry",
    name: "The Neon Foundry",
    label: "Foundry",
    kind: "business",
    bored: false,
    listed: true,
    placeId: "rail",
    appearance: { field: "rust", charge: "anchor", motto: "SUNDAY" },
    x: 230,
    y: 210,
    side: "s",
    intents: [{ kind: "sale", sentence: "Sunday backline, one night." }],
    note: "Business flag. Sunday backline, one night.",
  },
];

export const YOU_ID = "you";
export const NEAR_RADIUS = 150;

export function placeById(id) {
  return PLACES.find((place) => place.id === id);
}

export function personById(id) {
  return PEOPLE.find((person) => person.id === id);
}

export function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

export function boredNearby(people = PEOPLE, youId = YOU_ID, radius = NEAR_RADIUS) {
  const you = people.find((person) => person.id === youId);
  if (!you) return [];
  return people.filter((person) => person.id !== youId && person.bored && distance(person, you) <= radius);
}
