// Zine graph scene: nodes + edges with positions from the force layout.
// Used by the SVG node map (dims 2) and the AR scene (dims 3).

import { layout } from "../layout/force.js";

export const NODE_TYPES = {
  article: { label: "Article", glyph: "circle" },
  review: { label: "Review", glyph: "diamond" },
  letter: { label: "Letter", glyph: "square" },
  editorial: { label: "Editorial", glyph: "triangle" },
  event: { label: "Event", glyph: "circle" },
  venue: { label: "Venue", glyph: "hexagon" },
  entity: { label: "Entity", glyph: "ring" },
  missing: { label: "Not written yet", glyph: "ring" },
};
export const typeOf = t => NODE_TYPES[t] || NODE_TYPES.entity;

const ZINE = new URL("../../data/zine.json", import.meta.url).href;
let cached = null;
/** Load the built zine graph (web/data/zine.json, made by tools/build_zine.py). */
export function loadZine() {
  cached ||= fetch(ZINE).then(r => (r.ok ? r.json() : { nodes: [], edges: [] })).catch(() => ({ nodes: [], edges: [] }));
  return cached;
}

/**
 * Zine graph with positions. dims = 2 for the SVG map, 3 for the AR scene.
 * Same seed, same ids, so a node keeps its identity across renderers.
 */
export function graphScene(zine, { dims = 2, size = 1000 } = {}) {
  const nodes = zine.nodes.map(n => ({ ...n }));
  const ids = new Set(nodes.map(n => n.id));
  const edges = zine.edges.filter(e => ids.has(e.source) && ids.has(e.target)).map(e => ({ ...e }));
  const degree = new Map(nodes.map(n => [n.id, 0]));
  for (const e of edges) { degree.set(e.source, degree.get(e.source) + 1); degree.set(e.target, degree.get(e.target) + 1); }
  for (const n of nodes) n.degree = degree.get(n.id);
  layout(nodes, edges, { dims, size });
  return { kind: "graph", dims, nodes, edges, byId: new Map(nodes.map(n => [n.id, n])) };
}

export function neighbors(graph, id) {
  const out = new Set();
  for (const e of graph.edges) {
    if (e.source === id) out.add(e.target);
    if (e.target === id) out.add(e.source);
  }
  return out;
}
