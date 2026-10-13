// "/zine/" — Umwelt Horizons AVR+JIT Zine
// The spatial dispatches landscape: every article is an interactive spatial box
// on the page showcasing rich previews, bidirectional backlinks, and real-time
// connection highlights across the downtown AR scape.
// URL state: ?node=<id>, ?view=<boxes|split|graph>, ?filter=<cluster>

import { h, params, setParam, emit } from "../core/dom.js";
import "../core/theme.js";
import { SITE } from "../core/site.js";
import { loadZine, graphScene, NODE_TYPES, neighbors, getBacklinks, getOutgoingLinks, getConnectedNodes } from "../data/graph.js";
import { loadCalendar } from "../data/calendar.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";
import { nodeMap } from "../../components/node-map/node-map.js";
import { zineReader } from "../../components/zine-reader/zine-reader.js";
import { zineCard, nodeTypeTag } from "../../components/zine-card/zine-card.js";
import { button } from "../../components/button/button.js";

const app = document.getElementById("app");
const [zine, calendar] = await Promise.all([loadZine(), loadCalendar()]);
const graph = graphScene(zine, { dims: 2 });
const q = params();

const ARTICLE_TYPES = new Set([
  "article", "review", "letter", "editorial", "stance",
  "dossier", "dossier-piece", "prediction", "topic-overview", "topic-report"
]);

const allArticles = graph.nodes.filter(n => ARTICLE_TYPES.has(n.type) || n.html);
const notesCount = allArticles.length;
const venuesCount = graph.nodes.filter(n => n.type === "venue").length;
const eventsCount = graph.nodes.filter(n => n.type === "event").length;

let current = graph.byId.has(q.get("node")) ? q.get("node") : "";
// Default view is "boxes" (Spatial Boxes Scape)
let view = q.get("view") || (current ? "split" : "boxes");
let filter = q.get("filter") || "all";

function matchCluster(node, clusterKey) {
  if (clusterKey === "all") return true;
  const text = [
    node.title, node.summary || "", ...(node.tags || []), node.type || ""
  ].join(" ").toLowerCase();

  if (clusterKey === "climate") {
    return text.includes("climate") || text.includes("pacific") || text.includes("el-nino") ||
           text.includes("weather") || text.includes("enso") || text.includes("odds") ||
           node.type === "prediction";
  }
  if (clusterKey === "noise") {
    return text.includes("noise") || text.includes("acoustic") || text.includes("baffle") ||
           text.includes("decibel") || text.includes("surveillance") || text.includes("ordinance") ||
           node.type === "stance" || node.id.includes("noise-ordinance");
  }
  if (clusterKey === "loom") {
    return text.includes("loom") || text.includes("weaving") || text.includes("thoughts") ||
           text.includes("jacquard") || text.includes("machine") || text.includes("llm") ||
           text.includes("automation") || text.includes("checklist");
  }
  if (clusterKey === "venues") {
    return text.includes("midnight") || text.includes("late show") || text.includes("theatre") ||
           text.includes("lounge") || text.includes("baffle") || node.type === "review" ||
           (node.links || []).some(l => l.type === "venue") ||
           (node.backlinks || []).some(b => b.type === "venue");
  }
  return true;
}

function getClusterCount(clusterKey) {
  return allArticles.filter(n => matchCluster(n, clusterKey)).length;
}

// 1. Intro Header
const intro = h("header.nc-zine__intro", {},
  h("p.nc-eyebrow", {},
    h("img", { src: "/assets/brand/uh-crimson-256.png", alt: "", width: "20", height: "13", style: "vertical-align: middle; margin-inline-end: 6px; display: inline-block;" }),
    "Umwelt Horizons (The Zine)"
  ),
  h("h1.nc-h1", {}, "Editorial Dispatches & Field Dossiers"),
  h("p.nc-lede", {},
    `${notesCount} regional essays & dispatches, ${venuesCount} downtown rooms, and ${eventsCount} scheduled shows. Each article is an interactive spatial box in our AR landscape—hover any box to reveal its connected network, trace bidirectional backlinks, or click to open.`
  ),
);

// 2. View Switcher
const viewSwitch = h("fieldset.nc-segmented", {},
  h("legend.nc-label", {}, "Layout Mode"),
  h("div.nc-segmented__options", {},
    [["boxes", "Spatial Boxes Scape"], ["split", "Split Reader"], ["graph", "Entity Graph"]].map(([v, t]) =>
      h("label.nc-segmented__option", {},
        h("input", { type: "radio", name: "zine-view", value: v, checked: v === view }),
        h("span", {}, t)
      )
    )
  )
);

// 3. Legend
const legend = h("ul.nc-zine__legend", { role: "list", "aria-label": "Legend" },
  Object.keys(NODE_TYPES).filter(t => graph.nodes.some(n => n.type === t)).map(t => h("li", {}, nodeTypeTag(t)))
);

// 4. Constellation Filter Chips
const filterBar = h("div.nc-zine__filters", { role: "region", "aria-label": "Constellation Filter" });

function renderFilterBar() {
  filterBar.replaceChildren(
    h("span.nc-label", { style: "align-self: center; font-size: var(--nc-font-size-xs);" }, "Constellation:"),
    ...[
      ["all", `All Dispatches (${notesCount})`],
      ["climate", `Climate & El Niño (${getClusterCount("climate")})`],
      ["noise", `Noise & Stances (${getClusterCount("noise")})`],
      ["loom", `Automations & The Loom (${getClusterCount("loom")})`],
      ["venues", `Downtown Rooms (${getClusterCount("venues")})`],
    ].map(([k, label]) => {
      const chip = h("button.nc-filter-chip", {
        type: "button",
        "data-filter": k,
        "aria-pressed": String(filter === k),
      }, label);
      if (filter === k) chip.classList.add("is-active");
      chip.addEventListener("click", () => setFilter(k));
      return chip;
    })
  );
}
renderFilterBar();

// 5. Active Reader Container
const activeReaderWrapper = h("section.nc-zine__active-reader-wrapper", {
  "aria-label": "Active Dispatch Reader",
  hidden: !current
});
const readerNav = h("div.nc-zine__reader-nav", {});
const reader = h("div.nc-zine__reader", { "aria-live": "polite" });
const entityPods = h("aside.nc-zine__pods", { "aria-label": "Connected Entity Pods" });
const readLayout = h("div.nc-zine__read-layout", {}, reader, entityPods);
activeReaderWrapper.append(readerNav, readLayout);

// 6. Map View
const map = nodeMap(graph, { selectedId: current, label: "Umwelt Horizons entity graph" });
const mapView = h("div.nc-zine__layout", { hidden: view !== "graph" }, map);

// 7. Spatial Articles Grid
const gridHeading = h("div.nc-zine__grid-heading", {},
  h("h2", {}, current ? "More Dispatches in the Grid" : "All Dispatches & Field Dossiers"),
  h("p.nc-muted", { style: "font-size: var(--nc-font-size-sm); margin: 0;" },
    "Hover any box to light up its connected peers across the AR scape."
  )
);
const boxesGrid = h("div.nc-zine__grid", { role: "list", "aria-label": "Articles Grid" });
const gridSection = h("section.nc-zine__grid-section", { "aria-label": "Dispatches Grid" },
  gridHeading,
  boxesGrid
);

// Main DOM
const main = h("main.nc-container.nc-page.nc-zine", { id: "main", tabindex: "-1" },
  intro,
  h("div.nc-zine__bar", {}, legend, viewSwitch),
  filterBar,
  activeReaderWrapper,
  mapView,
  gridSection
);

app.replaceChildren(siteHeader(), main, siteFooter({ notes: calendar.notes, source: calendar.source }));

function renderGrid() {
  boxesGrid.replaceChildren();
  const visible = allArticles.filter(n => matchCluster(n, filter));
  if (!visible.length) {
    boxesGrid.append(h("p.nc-muted", {}, "No dispatches found in this constellation."));
    return;
  }
  for (const node of visible) {
    const card = zineCard(node, {
      level: 3,
      graph,
      spatial: true,
      active: node.id === current,
      showBacklinks: true
    });
    boxesGrid.append(card);
  }
}

function updatePods(node) {
  entityPods.replaceChildren();
  const near = [...neighbors(graph, node.id)].map(n => graph.byId.get(n)).filter(Boolean);
  if (!near.length) return;
  entityPods.append(
    h("h2.nc-zine__sub", {
      style: "font-size: var(--nc-font-size-sm); text-transform: uppercase; letter-spacing: var(--nc-font-tracking-caps); color: var(--nc-color-text-muted); margin-bottom: var(--nc-space-3);"
    }, `Connected Peers (${near.length})`),
    h("ul", { role: "list", style: "display: grid; gap: var(--nc-space-2); list-style: none; padding: 0; margin: 0;" },
      near.map(n => h("li", {}, zineCard(n, { level: 3, graph, spatial: false })))
    )
  );
}

function renderReaderNav(node) {
  readerNav.replaceChildren();

  const backBtn = button({
    label: `← Back to All Dispatches (${notesCount})`,
    variant: "outline",
    size: "sm",
    onClick: () => clearCurrent()
  });

  const titleSpan = h("span", {
    style: "font-size: var(--nc-font-size-sm); font-weight: var(--nc-font-weight-bold); color: var(--nc-color-accent);"
  }, `📖 Reading: ${node.title}`);

  readerNav.append(backBtn, titleSpan);
}

function read(id, { focus = true, push = true } = {}) {
  const node = graph.byId.get(id);
  if (!node) return;
  current = id;
  if (push) setParam("node", id, { replace: false });

  activeReaderWrapper.hidden = false;
  renderReaderNav(node);
  reader.replaceChildren(zineReader(node, { graph, calendar }));
  updatePods(node);
  map.select(id);

  gridHeading.querySelector("h2").textContent = "More Dispatches in the Grid";
  renderGrid();

  document.title = `${node.title} — ${SITE.zineName} zine`;

  if (focus) {
    const title = reader.querySelector(".nc-reader__title");
    title?.focus({ preventScroll: true });
    activeReaderWrapper.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }
}

function clearCurrent() {
  current = "";
  setParam("node", "");
  activeReaderWrapper.hidden = true;
  gridHeading.querySelector("h2").textContent = "All Dispatches & Field Dossiers";
  renderGrid();
  document.title = `${SITE.zineName} — Editorial Dispatches & Field Dossiers`;
  gridSection.scrollIntoView({ block: "start", behavior: "smooth" });
}

function setView(v, { push = true } = {}) {
  view = v;
  mapView.hidden = v !== "graph";
  if (v === "boxes") {
    // Spatial boxes scape is primary
    gridSection.hidden = false;
  } else if (v === "split") {
    gridSection.hidden = false;
  } else if (v === "graph") {
    gridSection.hidden = false;
  }

  viewSwitch.querySelectorAll("input").forEach(i => { i.checked = i.value === v; });
  if (push) setParam("view", v === "boxes" ? "" : v);
}

function setFilter(k) {
  filter = k;
  renderFilterBar();
  renderGrid();
  setParam("filter", k === "all" ? "" : k);
}

// Event Listeners
main.addEventListener("nc-select", e => {
  if (e.detail.kind === "node") read(e.detail.id);
});

viewSwitch.addEventListener("change", e => setView(e.target.value));

window.addEventListener("popstate", () => {
  const id = params().get("node");
  if (id && graph.byId.has(id)) {
    read(id, { push: false, focus: false });
  } else if (!id && current) {
    clearCurrent();
  }
});

// Initial Render
setView(view, { push: false });
renderGrid();

if (current) {
  read(current, { focus: false, push: false });
} else {
  // Page lands on full boxes scape with all articles visible!
  activeReaderWrapper.hidden = true;
}
