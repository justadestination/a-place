import { h, svg, emit } from "../../js/core/dom.js";
import { glyphPath } from "../glyph.js";
import { typeOf, graphScene, loadZine, neighbors } from "../../js/data/graph.js";
import { bounds } from "../../js/layout/force.js";
import { button } from "../button/button.js";
import { zineCard } from "../zine-card/zine-card.js";

let uid = 0;
const NOTE = new Set(["article", "review", "letter", "editorial"]);
const ZOOM = { min: 0.4, max: 4, step: 1.35, labels: 1.5 };

const icon = d => {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true"); s.setAttribute("fill", "none");
  s.setAttribute("stroke", "currentColor"); s.setAttribute("stroke-width", "2.25"); s.setAttribute("stroke-linecap", "round");
  s.innerHTML = d;
  return s;
};

/**
 * Obsidian-style map of the zine. Nodes are notes, events, venues and
 * unresolved links; edges are [[wiki-links]] and frontmatter relations.
 *
 * Pointer: drag to pan, wheel/pinch to zoom, click a node to open it.
 * Keyboard: one tab stop; arrows move to the nearest node in that direction,
 * Enter/Space opens it, + / - zoom, 0 fits everything.
 * Fires nc-select {kind:"node", id}. Call .select(id) to highlight from outside.
 */
export function nodeMap(graph, { selectedId = "", label = "Zine map" } = {}) {
  const id = `nc-map-${++uid}`;
  const box = bounds(graph.nodes, 60);
  const view = { k: 1, x: 0, y: 0 };
  let selected = selectedId;
  let focused = selectedId || graph.nodes.find(n => NOTE.has(n.type))?.id || graph.nodes[0]?.id;

  const edgeEls = new Map();
  const nodeEls = new Map();
  const edgesG = svg("g", { class: "nc-map__edges" });
  for (const e of graph.edges) {
    const a = graph.byId.get(e.source), b = graph.byId.get(e.target);
    const line = svg("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, "data-kind": e.kind });
    edgeEls.set(e, line);
    edgesG.append(line);
  }
  const nodesG = svg("g", { class: "nc-map__nodes" });
  const marks = [];
  for (const n of graph.nodes) {
    const t = typeOf(n.type);
    // Marks are drawn in screen pixels (see setView), so dots and labels stay
    // readable at every zoom and screen size; zooming spreads them apart.
    const r = NOTE.has(n.type) ? 12 : Math.min(11, 6 + n.degree);
    const labelText = n.title.length > 42 ? `${n.title.slice(0, 40)}…` : n.title;
    const mark = svg("g", { class: "nc-map__mark" },
      svg("circle", { class: "nc-map__hit", r: 22 }),
      svg("path", { class: "nc-map__shape", d: glyphPath(t.glyph, r) }),
      svg("text", { class: "nc-map__label", y: r + 18, "text-anchor": "middle" }, labelText),
    );
    marks.push(mark);
    const g = svg("g", {
      class: "nc-map__node", "data-node-type": n.type, "data-id": n.id, "data-note": NOTE.has(n.type) ? "true" : null,
      role: "button", tabindex: n.id === focused ? "0" : "-1",
      "aria-label": `${t.label}: ${n.title}. ${n.degree} link${n.degree === 1 ? "" : "s"}.`,
      transform: `translate(${n.x.toFixed(1)} ${n.y.toFixed(1)})`,
    }, mark);
    nodeEls.set(n.id, g);
    nodesG.append(g);
  }
  const viewport = svg("g", { class: "nc-map__viewport" }, edgesG, nodesG);
  const canvas = svg("svg", {
    class: "nc-map__svg", id, viewBox: `${box.x} ${box.y} ${box.w} ${box.h}`,
    role: "group", "aria-label": `${label}: ${graph.nodes.length} items, ${graph.edges.length} links`,
    "aria-describedby": `${id}-help`, preserveAspectRatio: "xMidYMid meet",
  }, svg("rect", { class: "nc-map__bg", x: box.x - box.w, y: box.y - box.h, width: box.w * 3, height: box.h * 3 }), viewport);

  const zoomIn = button({ label: "Zoom in", variant: "secondary", hideLabel: true, icon: icon('<path d="M12 5v14M5 12h14"/>'), onClick: () => zoomBy(ZOOM.step) });
  const zoomOut = button({ label: "Zoom out", variant: "secondary", hideLabel: true, icon: icon('<path d="M5 12h14"/>'), onClick: () => zoomBy(1 / ZOOM.step) });
  const fit = button({ label: "Fit map", variant: "secondary", icon: icon('<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>'), onClick: () => setView({ k: 1, x: 0, y: 0 }) });

  const root = h("div.nc-map", { "data-zoomed": "false" },
    h("div.nc-map__stage", {}, canvas, h("div.nc-map__tools", {}, zoomIn, zoomOut, fit)),
    h("p.nc-map__help", { id: `${id}-help` }, "Drag to move, scroll or pinch to zoom, select a dot to read it. Keyboard: arrow keys move between items, Enter opens, plus and minus zoom."),
  );

  // --- view ---------------------------------------------------------------
  let screenScale = 1; // CSS px per user unit at zoom 1
  function setView(v) {
    view.k = Math.min(ZOOM.max, Math.max(ZOOM.min, v.k));
    view.x = v.x; view.y = v.y;
    viewport.setAttribute("transform", `translate(${view.x.toFixed(2)} ${view.y.toFixed(2)}) scale(${view.k.toFixed(3)})`);
    root.dataset.zoomed = String(view.k >= ZOOM.labels);
    const inv = `scale(${(1 / (view.k * screenScale)).toFixed(4)})`;
    for (const m of marks) m.setAttribute("transform", inv);
  }
  new ResizeObserver(() => {
    const rect = canvas.getBoundingClientRect();
    if (!rect.width) return;
    screenScale = Math.min(rect.width / box.w, rect.height / box.h);
    setView(view);
  }).observe(canvas);
  function userPoint(clientX, clientY) {
    const m = canvas.getScreenCTM();
    if (!m) return { x: 0, y: 0 };
    const p = new DOMPoint(clientX, clientY).matrixTransform(m.inverse());
    return { x: p.x, y: p.y };
  }
  function zoomAt(factor, p) {
    const k = Math.min(ZOOM.max, Math.max(ZOOM.min, view.k * factor));
    const f = k / view.k;
    setView({ k, x: p.x - (p.x - view.x) * f, y: p.y - (p.y - view.y) * f });
  }
  function zoomBy(factor) {
    const n = graph.byId.get(focused);
    const p = n ? { x: n.x * view.k + view.x, y: n.y * view.k + view.y } : { x: box.x + box.w / 2, y: box.y + box.h / 2 };
    zoomAt(factor, p);
  }
  function ensureVisible(n) {
    const sx = n.x * view.k + view.x, sy = n.y * view.k + view.y, pad = 40;
    let { x, y } = view;
    if (sx < box.x + pad) x += box.x + pad - sx;
    if (sx > box.x + box.w - pad) x -= sx - (box.x + box.w - pad);
    if (sy < box.y + pad) y += box.y + pad - sy;
    if (sy > box.y + box.h - pad) y -= sy - (box.y + box.h - pad);
    if (x !== view.x || y !== view.y) setView({ k: view.k, x, y });
  }

  // --- selection & focus ---------------------------------------------------
  function paintSelection() {
    const near = selected ? neighbors(graph, selected) : new Set();
    for (const [nid, g] of nodeEls) {
      g.classList.toggle("is-selected", nid === selected);
      g.classList.toggle("is-near", near.has(nid));
      g.setAttribute("aria-pressed", String(nid === selected));
    }
    for (const [e, line] of edgeEls) line.classList.toggle("is-active", !!selected && (e.source === selected || e.target === selected));
  }
  function focusNode(nid) {
    const g = nodeEls.get(nid);
    if (!g) return;
    nodeEls.get(focused)?.setAttribute("tabindex", "-1");
    focused = nid;
    g.setAttribute("tabindex", "0");
    g.focus({ preventScroll: true });
    ensureVisible(graph.byId.get(nid));
  }
  function choose(nid) {
    selected = nid;
    paintSelection();
    emit(root, "nc-select", { kind: "node", id: nid });
  }
  function nearest(fromId, dx, dy) {
    const a = graph.byId.get(fromId);
    let best = null, score = Infinity;
    for (const b of graph.nodes) {
      if (b.id === fromId) continue;
      const vx = b.x - a.x, vy = b.y - a.y;
      const along = vx * dx + vy * dy;
      if (along <= 0) continue;
      const across = Math.abs(vx * dy - vy * dx);
      const s = along + across * 2.5;
      if (s < score) { score = s; best = b.id; }
    }
    return best;
  }

  canvas.addEventListener("keydown", e => {
    const g = e.target.closest?.(".nc-map__node");
    const dir = { ArrowRight: [1, 0], ArrowLeft: [-1, 0], ArrowDown: [0, 1], ArrowUp: [0, -1] }[e.key];
    if (dir && g) { e.preventDefault(); const next = nearest(g.dataset.id, ...dir); if (next) focusNode(next); return; }
    if ((e.key === "Enter" || e.key === " ") && g) { e.preventDefault(); choose(g.dataset.id); return; }
    if (e.key === "+" || e.key === "=") { e.preventDefault(); zoomBy(ZOOM.step); }
    else if (e.key === "-" || e.key === "_") { e.preventDefault(); zoomBy(1 / ZOOM.step); }
    else if (e.key === "0") { e.preventDefault(); setView({ k: 1, x: 0, y: 0 }); }
    else if (e.key === "Home") { e.preventDefault(); focusNode(graph.nodes[0].id); }
  });
  canvas.addEventListener("focusin", e => {
    const g = e.target.closest?.(".nc-map__node");
    if (g && g.dataset.id !== focused) { nodeEls.get(focused)?.setAttribute("tabindex", "-1"); focused = g.dataset.id; g.setAttribute("tabindex", "0"); }
  });

  // --- pointer: pan, pinch, tap -------------------------------------------
  const pointers = new Map();
  let drag = null, moved = false, pinch = null;
  canvas.addEventListener("pointerdown", e => {
    canvas.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    moved = false;
    if (pointers.size === 1) drag = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, node: e.target.closest(".nc-map__node")?.dataset.id };
    if (pointers.size === 2) {
      const [p1, p2] = [...pointers.values()];
      pinch = { d: Math.hypot(p1.x - p2.x, p1.y - p2.y), k: view.k, mid: userPoint((p1.x + p2.x) / 2, (p1.y + p2.y) / 2), vx: view.x, vy: view.y };
      drag = null;
    }
  });
  canvas.addEventListener("pointermove", e => {
    if (!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pinch && pointers.size === 2) {
      const [p1, p2] = [...pointers.values()];
      const f = Math.hypot(p1.x - p2.x, p1.y - p2.y) / pinch.d;
      const k = Math.min(ZOOM.max, Math.max(ZOOM.min, pinch.k * f));
      const r = k / pinch.k;
      setView({ k, x: pinch.mid.x - (pinch.mid.x - pinch.vx) * r, y: pinch.mid.y - (pinch.mid.y - pinch.vy) * r });
      moved = true;
      return;
    }
    if (!drag) return;
    const scale = canvas.getScreenCTM()?.a || 1;
    const dx = (e.clientX - drag.x) / scale, dy = (e.clientY - drag.y) / scale;
    if (Math.abs(dx) + Math.abs(dy) > 3 / scale) moved = true;
    if (moved) { root.classList.add("is-panning"); setView({ k: view.k, x: drag.vx + dx, y: drag.vy + dy }); }
  });
  const end = e => {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch = null;
    if (drag && !moved && drag.node) { focusNode(drag.node); choose(drag.node); }
    if (!pointers.size) { drag = null; root.classList.remove("is-panning"); }
  };
  canvas.addEventListener("pointerup", end);
  canvas.addEventListener("pointercancel", end);
  canvas.addEventListener("wheel", e => {
    e.preventDefault();
    zoomAt(Math.exp(-e.deltaY * (e.deltaMode ? 0.05 : 0.0018)), userPoint(e.clientX, e.clientY));
  }, { passive: false });

  root.select = nid => { selected = nid; paintSelection(); const n = graph.byId.get(nid); if (n) ensureVisible(n); };
  root.focusNode = focusNode;
  setView(view);
  paintSelection();
  return root;
}

export const meta = {
  name: "node-map",
  title: "Zine node map",
  summary: "The zine as a force-directed graph: notes, events, venues and unresolved links. Pan, zoom, keyboard navigation, select to read.",
  params: { node: "node id to highlight" },
};

export async function embed(params, ctx) {
  const graph = graphScene(await (ctx.zine?.() || loadZine()), { dims: 2 });
  const map = nodeMap(graph, { selectedId: params.get("node") || "" });
  const card = h("div.nc-map-embed__card", { "aria-live": "polite" });
  const show = nid => { const n = graph.byId.get(nid); card.replaceChildren(n ? zineCard(n) : ""); };
  map.addEventListener("nc-select", e => {
    show(e.detail.id);
    ctx.select("node", e.detail.id, { url: new URL(`/zine/?node=${encodeURIComponent(e.detail.id)}`, location.origin).href, label: graph.byId.get(e.detail.id)?.title });
  });
  if (params.get("node")) show(params.get("node"));
  return h("div.nc-stack", {}, map, card);
}
