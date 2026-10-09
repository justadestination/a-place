import { h, emit } from "../../js/core/dom.js";
import { nodeTypeTag, byline, zineCard } from "../zine-card/zine-card.js";
import { eventCard } from "../event-card/event-card.js";
import { eventRow } from "../event-row/event-row.js";
import { shareButton } from "../share-button/share-button.js";
import { typeOf, graphScene, neighbors } from "../../js/data/graph.js";
import { label } from "../../js/data/dates.js";

let uid = 0;

/**
 * Reads one node. Notes show their (build-time rendered) body; events show
 * the event card; venues list what is on there; unresolved links say so.
 * Below, everything it links to. In-text [[links]] and linked cards fire
 * nc-select {kind:"node", id}.
 *   graph     graphScene() result
 *   calendar  optional CalendarModel, to show full event cards
 */
export function zineReader(node, { graph, calendar, level = 2 } = {}) {
  const id = `nc-reader-${++uid}`;
  const t = typeOf(node.type);
  const root = h("article.nc-reader", { "aria-labelledby": id, "data-node-type": node.type });
  const url = new URL(`/zine/?node=${encodeURIComponent(node.id)}`, location.origin).href;

  root.append(h("header.nc-reader__header", {},
    nodeTypeTag(node.type),
    h(`h${level}.nc-reader__title`, { id, tabindex: "-1" }, node.title),
    byline(node) ? h("p.nc-reader__meta", {}, byline(node), node.status && node.status !== "published" ? ` · ${node.status}` : "") : null,
  ));

  if (node.html) {
    root.append(h("div.nc-prose", { html: node.html }));
  } else if (node.type === "event" && calendar?.eventsById.get(node.ref)) {
    const ev = calendar.eventsById.get(node.ref);
    root.append(eventCard(ev, { venue: calendar.venuesById.get(ev.venueId), level: level + 1, today: calendar.today }));
  } else if (node.type === "venue" && calendar) {
    const venue = calendar.venuesById.get(node.ref);
    const upcoming = calendar.events.filter(e => e.venueId === node.ref && e.date >= calendar.today);
    root.append(
      venue?.address ? h("p.nc-lede", {}, venue.address) : null,
      h(`h${level + 1}.nc-reader__sub`, {}, upcoming.length ? "Coming up here" : "Nothing listed here right now"),
      upcoming.length ? h("ol.nc-reader__events", { role: "list" }, upcoming.slice(0, 8).map(e => h("li", {}, eventRow(e, { showDate: true, dateLabel: label.medium(e.date) })))) : null,
    );
  } else if (node.type === "missing") {
    root.append(h("p.nc-lede", {}, node.summary || "Nothing has been written for this link yet."));
  } else if (node.summary) {
    root.append(h("p.nc-lede", {}, node.summary));
  }

  if (graph) {
    const near = [...neighbors(graph, node.id)].map(n => graph.byId.get(n)).filter(Boolean)
      .sort((a, b) => (a.type === "missing") - (b.type === "missing") || a.title.localeCompare(b.title));
    if (near.length) {
      root.append(h("section.nc-reader__links", { "aria-labelledby": `${id}-links` },
        h(`h${level + 1}.nc-reader__sub`, { id: `${id}-links` }, `Linked from here (${near.length})`),
        h("ul.nc-reader__grid", { role: "list" }, near.map(n => h("li", {}, zineCard(n, { level: level + 2 })))),
      ));
    }
  }
  if (node.type !== "missing") root.append(h("div.nc-reader__actions", {}, shareButton({ title: node.title, text: `${t.label}: ${node.title}`, url })));

  root.addEventListener("click", e => {
    const a = e.target.closest("a[data-node]");
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey) return;
    e.preventDefault();
    emit(root, "nc-select", { kind: "node", id: a.dataset.node });
  });
  // Event rows inside a venue open the event's node.
  root.addEventListener("nc-select", e => {
    if (e.detail.kind === "event" && graph?.byId.has(`event:${e.detail.id}`)) {
      e.stopPropagation();
      emit(root, "nc-select", { kind: "node", id: `event:${e.detail.id}` });
    }
  });
  return root;
}

export const meta = {
  name: "zine-reader",
  title: "Zine reader",
  summary: "Reads one zine node (note, event, venue or unresolved link) and lists what it links to.",
  params: { node: "node id (defaults to the first note)" },
};

export async function embed(params, ctx) {
  const [zine, calendar] = await Promise.all([ctx.zine(), ctx.calendar()]);
  const graph = graphScene(zine, { dims: 2 });
  const holder = h("div", {});
  const show = nid => {
    const node = graph.byId.get(nid) || zine.nodes.find(n => n.html) || zine.nodes[0];
    if (!node) { holder.replaceChildren(h("p", {}, "The zine is empty.")); return; }
    holder.replaceChildren(zineReader(node, { graph, calendar }));
  };
  holder.addEventListener("nc-select", e => {
    if (e.detail.kind !== "node") return;
    show(e.detail.id);
    holder.querySelector(".nc-reader__title")?.focus();
    ctx.select("node", e.detail.id);
  });
  show(params.get("node"));
  return holder;
}
