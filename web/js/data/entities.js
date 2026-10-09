/**
 * Entity pages data (Task 2.13).
 * Promoters, bands, comedians, and other. No DOM imports.
 */

export const SEED_ENTITIES = [
  {
    id: "ent_promoter_lumen",
    type: "promoter",
    name: "Lumen Presents",
    status: "active",
    bio: "Books rooms and touring bills across Santa Rosa.",
    contact: {
      phones: [{ text: "+1-707-555-0142", href: "tel:+17075550142" }],
      emails: [{ text: "book@lumen.example", href: "mailto:book@lumen.example" }],
      websites: [{ text: "lumen.example", href: "https://lumen.example" }],
    },
  },
  {
    id: "ent_band_wave",
    type: "band",
    name: "Subterranean Wave Syndicate",
    status: "active",
    bio: "A late-set band that plays the cellar rooms.",
    contact: {
      phones: [{ text: "+1-707-555-0194", href: "tel:+17075550194" }],
      emails: [{ text: "wave@syndicate.example", href: "mailto:wave@syndicate.example" }],
      websites: [{ text: "wave.example", href: "https://wave.example" }],
    },
  },
  {
    id: "ent_comic_null",
    type: "comedian",
    name: "Mara Voss",
    status: "active",
    bio: "Stand-up comic who opens the Friday bills.",
    contact: {
      phones: [{ text: "+1-707-555-0177", href: "tel:+17075550177" }],
      emails: [{ text: "mara@voss.example", href: "mailto:mara@voss.example" }],
      websites: [{ text: "maravoss.example", href: "https://maravoss.example" }],
    },
  },
  {
    id: "ent_other_paper",
    type: "other",
    name: "Night Paper",
    status: "active",
    bio: "The printed zine that covers the same nights as the calendar.",
    contact: {
      phones: [],
      emails: [{ text: "desk@nightpaper.example", href: "mailto:desk@nightpaper.example" }],
      websites: [{ text: "nightpaper.example", href: "https://nightpaper.example" }],
    },
  },
];

export const SEED_EVENTS = [
  {
    id: "evt_wave_night",
    title: "Subterranean Wave Syndicate",
    date: "2026-10-12",
    start: "8:00 PM",
    venueId: "ven_a261886187f23bb1",
    entityIds: ["ent_band_wave", "ent_comic_null"],
    performers: [
      { name: "Subterranean Wave Syndicate", id: "ent_band_wave", type: "band" },
      { name: "Mara Voss", id: "ent_comic_null", type: "comedian" },
    ],
  },
];

export const SEED_ARTICLES = [
  {
    id: "zine_wave_note",
    type: "article",
    title: "A night with Subterranean Wave Syndicate",
    summary: "Notes from the cellar set.",
  },
];

export function entityHref(entity) {
  const id = encodeURIComponent(entity.id);
  const type = encodeURIComponent(entity.type || "other");
  return `/entity/?id=${id}&type=${type}`;
}

export function getEntity(id) {
  return SEED_ENTITIES.find(entity => entity.id === id) || null;
}

export function listEntities(type) {
  if (!type) return SEED_ENTITIES.slice();
  return SEED_ENTITIES.filter(entity => entity.type === type);
}

export function entityByName(name) {
  const wanted = String(name || "").trim().toLowerCase();
  if (!wanted) return null;
  return SEED_ENTITIES.find(entity => entity.name.toLowerCase() === wanted) || null;
}

function performerName(performer) {
  if (typeof performer === "string") return performer.trim();
  return String(performer?.name || "").trim();
}

function performerId(performer) {
  return typeof performer === "object" && performer ? String(performer.id || "") : "";
}

export function eventMatchesEntity(event, entity) {
  if (!event || !entity) return false;
  if ((event.entityIds || []).includes(entity.id)) return true;
  for (const performer of event.performers || []) {
    if (performerId(performer) === entity.id) return true;
    if (performerName(performer).toLowerCase() === entity.name.toLowerCase()) return true;
  }
  return false;
}

export function eventsForEntity(entity, events = SEED_EVENTS) {
  return (events || []).filter(event => eventMatchesEntity(event, entity));
}

export function entitiesForEvent(event, entities = SEED_ENTITIES) {
  return (entities || []).filter(entity => eventMatchesEntity(event, entity));
}

function containsName(blob, name) {
  const hay = String(blob || "").toLowerCase();
  const needle = String(name || "").toLowerCase();
  if (!needle) return false;
  let start = 0;
  while (start <= hay.length) {
    const found = hay.indexOf(needle, start);
    if (found < 0) return false;
    const beforeOk = found === 0 || !/[a-z0-9]/i.test(hay[found - 1]);
    const after = found + needle.length;
    const afterOk = after >= hay.length || !/[a-z0-9]/i.test(hay[after]);
    if (beforeOk && afterOk) return true;
    start = found + 1;
  }
  return false;
}

export function articleMatchesEntity(article, entity) {
  const listed = [...(article.entityIds || []), ...(article.entities || [])];
  if (listed.includes(entity.id)) return true;
  const blob = [article.title, article.body, article.summary, article.text, article.html].filter(Boolean).join(" ");
  return containsName(blob, entity.name);
}

export function articlesForEntity(entity, articles = SEED_ARTICLES) {
  return (articles || []).filter(article => articleMatchesEntity(article, entity));
}

export function linkifySegments(text, entities = SEED_ENTITIES) {
  const source = String(text || "");
  const sorted = entities.slice().sort((a, b) => b.name.length - a.name.length);
  const parts = [];
  let index = 0;
  while (index < source.length) {
    const rest = source.slice(index).toLowerCase();
    let hit = null;
    for (const entity of sorted) {
      const needle = entity.name.toLowerCase();
      if (!rest.startsWith(needle)) continue;
      const beforeOk = index === 0 || !/[a-z0-9]/i.test(source[index - 1]);
      const after = index + entity.name.length;
      const afterOk = after >= source.length || !/[a-z0-9]/i.test(source[after]);
      if (beforeOk && afterOk) {
        hit = entity;
        break;
      }
    }
    if (hit) {
      parts.push({ kind: "entity", text: source.slice(index, index + hit.name.length), entity: hit });
      index += hit.name.length;
      continue;
    }
    const last = parts[parts.length - 1];
    if (last && last.kind === "text") last.text += source[index];
    else parts.push({ kind: "text", text: source[index] });
    index += 1;
  }
  return parts;
}
