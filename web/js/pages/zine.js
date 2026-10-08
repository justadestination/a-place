// "/zine/" — the AVR+JIT zine. The node map IS the navigation: select a node
// to read it in the panel beside (or below) the map. A list view groups the
// same nodes by type for readers who prefer, or need, a linear page.
// URL state: ?node=<id>, ?view=list.
import { h, params, setParam } from "../core/dom.js";
import "../core/theme.js";
import { SITE } from "../core/site.js";
import { loadZine, graphScene, NODE_TYPES } from "../data/graph.js";
import { loadCalendar } from "../data/calendar.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";
import { nodeMap } from "../../components/node-map/node-map.js";
import { zineReader } from "../../components/zine-reader/zine-reader.js";
import { zineCard, nodeTypeTag } from "../../components/zine-card/zine-card.js";

const app = document.getElementById("app");
const [zine, calendar] = await Promise.all([loadZine(), loadCalendar()]);
const graph = graphScene(zine, { dims: 2 });
const q = params();
let view = q.get("view") === "list" ? "list" : "map";
let current = graph.byId.has(q.get("node")) ? q.get("node") : "";

const notes = graph.nodes.filter(n => n.html).length;
const count = t => graph.nodes.filter(n => n.type === t).length;
const intro = h("div.nc-zine__intro", {},
  h("p.nc-eyebrow", {}, `The ${SITE.zineName} zine`),
  h("h1.nc-h1", {}, "The zine, as a map"),
  h("p.nc-lede", {}, `${notes} ${notes === 1 ? "piece" : "pieces"} of writing, ${count("event")} shows, ${count("venue")} rooms, and ${count("missing")} links still to be written. Pick any dot to read it.`),
);

const viewSwitch = h("fieldset.nc-segmented", {},
  h("legend.nc-label", {}, "View"),
  h("div.nc-segmented__options", {}, [["map", "Map"], ["list", "List"]].map(([v, t]) =>
    h("label.nc-segmented__option", {}, h("input", { type: "radio", name: "zine-view", value: v, checked: v === view }), h("span", {}, t)))),
);
const legend = h("ul.nc-zine__legend", { role: "list", "aria-label": "Legend" },
  Object.keys(NODE_TYPES).filter(t => graph.nodes.some(n => n.type === t)).map(t => h("li", {}, nodeTypeTag(t))));

const map = nodeMap(graph, { selectedId: current, label: `${SITE.zineName} zine map` });
const reader = h("div.nc-zine__reader", { "aria-live": "polite" });
const mapView = h("div.nc-zine__layout", {}, map, reader);
const listView = h("div.nc-zine__list", {});
const main = h("main.nc-container.nc-page.nc-zine", { id: "main", tabindex: "-1" },
  intro, h("div.nc-zine__bar", {}, legend, viewSwitch), mapView, listView);
app.replaceChildren(siteHeader(), main, siteFooter({ notes: calendar.notes, source: calendar.source }));

function drawList() {
  const groups = Object.keys(NODE_TYPES).map(t => [t, graph.nodes.filter(n => n.type === t)]).filter(([, ns]) => ns.length);
  listView.replaceChildren(...groups.map(([t, ns]) => h("section.nc-zine__group", { "aria-labelledby": `grp-${t}` },
    h("h2", { id: `grp-${t}` }, `${NODE_TYPES[t].label}${ns.length === 1 ? "" : "s"} (${ns.length})`),
    h("ul.nc-zine__cards", { role: "list" }, ns.map(n => h("li", {}, zineCard(n)))))));
}

function read(id, { focus = true, push = true } = {}) {
  const node = graph.byId.get(id);
  if (!node) return;
  current = id;
  if (push) setParam("node", id, { replace: false });
  if (view === "list") setView("map", { push: false });
  reader.replaceChildren(zineReader(node, { graph, calendar }));
  map.select(id);
  document.title = `${node.title} — ${SITE.zineName} zine`;
  if (focus) {
    const title = reader.querySelector(".nc-reader__title");
    title?.focus({ preventScroll: true });
    if (getComputedStyle(reader).position !== "sticky") reader.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }
}

function setView(v, { push = true } = {}) {
  view = v;
  mapView.hidden = v !== "map";
  listView.hidden = v !== "list";
  if (v === "list" && !listView.childElementCount) drawList();
  viewSwitch.querySelectorAll("input").forEach(i => { i.checked = i.value === v; });
  if (push) setParam("view", v === "list" ? "" + v : "");
}

main.addEventListener("nc-select", e => { if (e.detail.kind === "node") read(e.detail.id); });
viewSwitch.addEventListener("change", e => setView(e.target.value));
window.addEventListener("popstate", () => {
  const id = params().get("node");
  if (id && graph.byId.has(id)) read(id, { push: false, focus: false });
});

setView(view, { push: false });
if (current) read(current, { focus: false, push: false });
else {
  // Open on the newest piece of writing so the panel is never empty.
  const first = graph.nodes.filter(n => n.html).sort((a, b) => (b.date || "").localeCompare(a.date || ""))[0];
  if (first) read(first.id, { focus: false, push: false });
}
