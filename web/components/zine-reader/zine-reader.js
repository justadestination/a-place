import { h, emit } from "../../js/core/dom.js";
import { entityHref, linkifySegments } from "../../js/data/entities.js";
import { nodeTypeTag, byline, zineCard } from "../zine-card/zine-card.js";
import { eventCard } from "../event-card/event-card.js";
import { eventRow } from "../event-row/event-row.js";
import { shareButton } from "../share-button/share-button.js";
import { correctionsUI, getCorrections } from "../corrections/corrections.js";
import { typeOf, graphScene, neighbors, getBacklinks, getOutgoingLinks } from "../../js/data/graph.js";
import { label } from "../../js/data/dates.js";
import { button } from "../button/button.js";
import { isStewardActive, openStewardDrawer } from "../steward-drawer/steward-drawer.js";

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
    const incoming = getBacklinks(graph, node.id).filter(n => n.type !== "missing");
    const outgoing = getOutgoingLinks(graph, node.id).filter(n => n.type !== "missing");

    const connectionsSec = h("section.nc-reader__backlinks-dock", { "aria-labelledby": `${id}-conns` },
      h(`h${level + 1}.nc-reader__sub`, { id: `${id}-conns` }, `Bidirectional Backlinks & Relational Scape`)
    );

    let hasConns = false;
    if (incoming.length > 0) {
      hasConns = true;
      connectionsSec.append(
        h("div.nc-reader__conn-block", {},
          h(`h${level + 2}.nc-eyebrow`, {}, `↩ Referenced By (${incoming.length} incoming backlinks)`),
          h("p.nc-reader__conn-desc", {}, "Other dispatches and dossiers that cite and link into this piece:"),
          h("ul.nc-reader__grid", { role: "list" }, incoming.map(n => h("li", {}, zineCard(n, { level: level + 3, graph, spatial: false }))))
        )
      );
    }

    const venues = outgoing.filter(n => n.type === "venue");
    if (venues.length > 0) {
      hasConns = true;
      connectionsSec.append(
        h("div.nc-reader__conn-block", {},
          h(`h${level + 2}.nc-eyebrow`, {}, `🏛️ Downtown Venues & Rooms Cited (${venues.length})`),
          h("p.nc-reader__conn-desc", {}, "Physical rooms and stages referenced directly in this piece:"),
          h("ul.nc-reader__grid", { role: "list" }, venues.map(n => h("li", {}, zineCard(n, { level: level + 3, graph, spatial: false }))))
        )
      );
    }

    const outgoingNotes = outgoing.filter(n => n.type !== "venue");
    if (outgoingNotes.length > 0) {
      hasConns = true;
      connectionsSec.append(
        h("div.nc-reader__conn-block", {},
          h(`h${level + 2}.nc-eyebrow`, {}, `↪ Referenced Dispatches & Topics (${outgoingNotes.length})`),
          h("p.nc-reader__conn-desc", {}, "Connected dispatches, stances, and research reports:"),
          h("ul.nc-reader__grid", { role: "list" }, outgoingNotes.map(n => h("li", {}, zineCard(n, { level: level + 3, graph, spatial: false }))))
        )
      );
    }

    if (hasConns) {
      root.append(connectionsSec);
    }
  }
  if (node.type !== "missing") {
    // Reactions and Comments section (gated by Steward)
    let likes = 14;
    let dislikes = 1;
    const reactionNotice = h("div.nc-reader__reaction-notice", { style: { display: "none", fontSize: "var(--nc-font-size-sm)", color: "var(--nc-color-accent)", marginTop: "var(--nc-space-2)" } });

    const likeBtn = button({
      label: `👍 Helpful (${likes})`,
      variant: "outline",
      onClick: () => {
        if (!isStewardActive()) {
          openStewardDrawer("Reacting to or rating zine dispatches requires an active Steward and 21+ verification.");
          return;
        }
        likes++;
        likeBtn.textContent = `👍 Helpful (${likes})`;
        reactionNotice.textContent = "Reaction recorded through your Personal Steward.";
        reactionNotice.style.display = "block";
      }
    });

    const dislikeBtn = button({
      label: `👎 Disputed (${dislikes})`,
      variant: "outline",
      onClick: () => {
        if (!isStewardActive()) {
          openStewardDrawer("Reacting to or rating zine dispatches requires an active Steward and 21+ verification.");
          return;
        }
        dislikes++;
        dislikeBtn.textContent = `👎 Disputed (${dislikes})`;
        reactionNotice.textContent = "Dispute note recorded for editorial calibration.";
        reactionNotice.style.display = "block";
      }
    });

    const letterBtn = button({
      label: "✉️ Write Letter to Editor",
      variant: "ghost",
      onClick: () => {
        if (!isStewardActive()) {
          openStewardDrawer("Submitting letters to the editor requires an active Steward and 21+ verification.");
          return;
        }
        const text = prompt(`Write letter to the editor regarding "${node.title}":`);
        if (!text) return;
        reactionNotice.textContent = "Your letter was queued for autonomous fact-checking and editor review.";
        reactionNotice.style.display = "block";
      }
    });

    const reactionBar = h("div.nc-stack", {
      style: {
        marginTop: "var(--nc-space-4)",
        padding: "var(--nc-space-4)",
        background: "var(--nc-color-surface)",
        border: "1px solid var(--nc-color-border)",
        borderRadius: "var(--nc-radius-md)",
        gap: "var(--nc-space-2)"
      }
    },
      h("p.nc-eyebrow", {}, "Dispatch Feedback & Reactions"),
      h("div.nc-cluster", { style: { gap: "var(--nc-space-2)", flexWrap: "wrap" } },
        likeBtn,
        dislikeBtn,
        letterBtn
      ),
      reactionNotice
    );

    root.append(reactionBar);
    root.append(correctionsUI(node.id, { level: level + 1 }));
    root.append(h("div.nc-reader__actions", {}, shareButton({ title: node.title, text: `${t.label}: ${node.title}`, url })));
  }

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
  linkifyEntityNames(root);
  return root;
}

function linkifyEntityNames(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const texts = [];
  while (walker.nextNode()) texts.push(walker.currentNode);
  for (const node of texts) {
    if (node.parentElement?.closest("a, button, script, style")) continue;
    const parts = linkifySegments(node.nodeValue || "");
    if (parts.every(part => part.kind === "text")) continue;
    const frag = document.createDocumentFragment();
    for (const part of parts) {
      if (part.kind === "text") frag.append(document.createTextNode(part.text));
      else frag.append(h("a.nc-entity-link", { href: entityHref(part.entity) }, part.text));
    }
    node.parentNode.replaceChild(frag, node);
  }
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
