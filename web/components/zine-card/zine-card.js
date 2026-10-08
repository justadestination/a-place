import { h, emit } from "../../js/core/dom.js";
import { glyph } from "../glyph.js";
import { typeOf, NODE_TYPES } from "../../js/data/graph.js";

/** Type label with its shape, coloured from the node-<type> token. */
export function nodeTypeTag(type) {
  const t = typeOf(type);
  return h("span.nc-node-type", { "data-node-type": type }, glyph(t.glyph), h("span", {}, t.label));
}

export function byline(node) {
  const author = (node.author || "").replace(/^a2a:\/\/agent\//, "agent ");
  return [node.date, author].filter(Boolean).join(" · ");
}

/**
 * Summary card for one zine node. The title is a real link (/zine/?node=id)
 * so it works without script; with script it fires nc-select {kind:"node", id}.
 */
export function zineCard(node, { level = 3 } = {}) {
  const link = h("a.nc-zine-card__link", { href: `/zine/?node=${encodeURIComponent(node.id)}` }, node.title);
  link.addEventListener("click", e => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    e.preventDefault();
    emit(link, "nc-select", { kind: "node", id: node.id });
  });
  return h("article.nc-zine-card", { "data-node-type": node.type },
    nodeTypeTag(node.type),
    h(`h${level}.nc-zine-card__title`, {}, link),
    byline(node) ? h("p.nc-zine-card__meta", {}, byline(node)) : null,
    node.summary ? h("p.nc-zine-card__summary", {}, node.summary) : null,
  );
}

export const meta = {
  name: "zine-card",
  title: "Zine card",
  summary: "One zine node as a card: type, title link, byline, summary. Works without script.",
  params: { node: "node id (defaults to the first note)", type: "article | review | letter | editorial | event | venue | missing" },
};

export async function embed(params, ctx) {
  const zine = await ctx.zine();
  const type = params.get("type");
  const node = zine.nodes.find(n => n.id === params.get("node")) || zine.nodes.find(n => (type ? n.type === type : n.html)) || zine.nodes[0];
  if (!node) return h("p.nc-muted", {}, "The zine is empty.");
  const card = zineCard(node, { level: 2 });
  card.addEventListener("nc-select", e => ctx.select("node", e.detail.id, { url: new URL(`/zine/?node=${e.detail.id}`, location.origin).href }));
  return card;
}
