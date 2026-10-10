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
export function zineCard(node, { level = 3, showBacklinks = true, graph = null, active = false, spatial = true } = {}) {
  const link = h("a.nc-zine-card__link", { href: `/zine/?node=${encodeURIComponent(node.id)}` }, node.title);
  const card = h("article.nc-zine-card", {
    "data-node-type": node.type,
    "data-node-id": node.id,
    tabindex: "0",
    role: "article",
    "aria-label": `${node.title} (${typeOf(node.type).label})`
  });

  if (active) card.classList.add("is-active");
  if (spatial) card.classList.add("nc-zine-card--spatial");

  const clickHandler = e => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    if (e.target.closest(".nc-zine-card__pill")) return; // let pill handle its own navigation
    e.preventDefault();
    emit(card, "nc-select", { kind: "node", id: node.id });
  };
  link.addEventListener("click", clickHandler);
  card.addEventListener("click", clickHandler);
  card.addEventListener("keydown", e => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      emit(card, "nc-select", { kind: "node", id: node.id });
    }
  });

  // Collect incoming and outgoing connections
  let incoming = (node.backlinks || []).filter(b => b.type !== "missing");
  let outgoing = (node.links || []).filter(l => l.type !== "missing");

  if (graph) {
    if (!incoming.length) {
      for (const e of graph.edges) {
        if (e.target === node.id && e.source !== node.id) {
          const src = graph.byId.get(e.source);
          if (src && src.type !== "missing" && !incoming.some(x => x.id === src.id)) {
            incoming.push({ id: src.id, title: src.title, type: src.type, kind: e.kind });
          }
        }
      }
    }
    if (!outgoing.length) {
      for (const e of graph.edges) {
        if (e.source === node.id && e.target !== node.id) {
          const tgt = graph.byId.get(e.target);
          if (tgt && tgt.type !== "missing" && !outgoing.some(x => x.id === tgt.id)) {
            outgoing.push({ id: tgt.id, title: tgt.title, type: tgt.type, kind: e.kind });
          }
        }
      }
    }
  }

  const connectedIds = new Set([...incoming.map(x => x.id), ...outgoing.map(x => x.id)]);
  if (graph) {
    for (const e of graph.edges) {
      if (e.source === node.id) connectedIds.add(e.target);
      if (e.target === node.id) connectedIds.add(e.source);
    }
  }
  card.setAttribute("data-connected-ids", [...connectedIds].join(" "));

  card.append(
    h("header.nc-zine-card__header", {},
      nodeTypeTag(node.type),
      byline(node) ? h("span.nc-zine-card__meta", {}, byline(node)) : null,
    ),
    h(`h${level}.nc-zine-card__title`, {}, link),
    node.summary ? h("p.nc-zine-card__summary", {}, node.summary) : null,
  );

  if (showBacklinks && (incoming.length > 0 || outgoing.length > 0)) {
    const connContainer = h("div.nc-zine-card__connections", {});
    if (incoming.length > 0) {
      const incRow = h("div.nc-zine-card__conn-row", {},
        h("span.nc-zine-card__conn-badge", {}, `↩ Backlinks (${incoming.length}):`),
        ...incoming.slice(0, 3).map(b => {
          const pill = h("a.nc-zine-card__pill", {
            href: `/zine/?node=${encodeURIComponent(b.id)}`,
            "data-node": b.id,
            title: b.title
          }, b.title);
          pill.addEventListener("click", ev => {
            ev.preventDefault();
            ev.stopPropagation();
            emit(card, "nc-select", { kind: "node", id: b.id });
          });
          return pill;
        }),
        incoming.length > 3 ? h("span.nc-zine-card__pill-more", {}, `+${incoming.length - 3}`) : null,
      );
      connContainer.append(incRow);
    }
    if (outgoing.length > 0) {
      const outRow = h("div.nc-zine-card__conn-row", {},
        h("span.nc-zine-card__conn-badge", {}, `↪ Links (${outgoing.length}):`),
        ...outgoing.slice(0, 3).map(l => {
          const pill = h("a.nc-zine-card__pill", {
            href: `/zine/?node=${encodeURIComponent(l.id)}`,
            "data-node": l.id,
            title: l.title
          }, l.title);
          pill.addEventListener("click", ev => {
            ev.preventDefault();
            ev.stopPropagation();
            emit(card, "nc-select", { kind: "node", id: l.id });
          });
          return pill;
        }),
        outgoing.length > 3 ? h("span.nc-zine-card__pill-more", {}, `+${outgoing.length - 3}`) : null,
      );
      connContainer.append(outRow);
    }
    card.append(connContainer);
  }

  const footer = h("footer.nc-zine-card__footer", {},
    h("span.nc-zine-card__read-btn", {}, active ? "Currently Reading 📖" : "Read Dispatch →"),
    (incoming.length + outgoing.length > 0)
      ? h("span.nc-zine-card__conn-count", {}, `🔗 ${incoming.length + outgoing.length} relations`)
      : null,
  );
  card.append(footer);

  if (spatial) {
    card.addEventListener("mouseenter", () => {
      card.classList.add("is-hovered");
      const container = card.closest(".nc-zine__cards, .nc-zine, .nc-page") || document;
      const cards = container.querySelectorAll("[data-node-id]");
      cards.forEach(c => {
        const cid = c.getAttribute("data-node-id");
        if (cid === node.id) {
          c.classList.add("is-focused-node");
        } else if (connectedIds.has(cid)) {
          c.classList.add("is-connected-peer");
        } else {
          c.classList.add("is-dimmed");
        }
      });
    });
    card.addEventListener("mouseleave", () => {
      card.classList.remove("is-hovered");
      const container = card.closest(".nc-zine__cards, .nc-zine, .nc-page") || document;
      const cards = container.querySelectorAll("[data-node-id]");
      cards.forEach(c => {
        c.classList.remove("is-focused-node", "is-connected-peer", "is-dimmed");
      });
    });
  }

  return card;
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
