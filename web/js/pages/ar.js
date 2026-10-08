// "/3d/" — AR preview. Progressive enhancement: the page works (as a list
// that links back to 2D) with no WebGL; three.js loads only when WebGL exists.
// Week and zine come from the same scene models as the 2D components.
import { h, params, setParam } from "../core/dom.js";
import "../core/theme.js";
import { loadCalendar } from "../data/calendar.js";
import { weekScene } from "../data/scene.js";
import { loadZine, graphScene } from "../data/graph.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";
import { button } from "../../components/button/button.js";
import { eventRow } from "../../components/event-row/event-row.js";

const app = document.getElementById("app");
const [model, zine] = await Promise.all([loadCalendar(), loadZine()]);
const q = params();
let mode = q.get("mode") === "graph" ? "graph" : "week";
// Open on the first week that has something in it, so the scene is never empty.
const firstNight = model.events.find(e => e.night && e.date >= model.today)?.date || model.today;
const week = weekScene(model, { date: firstNight, scope: "nights" });
const graph3 = graphScene(zine, { dims: 3 });

const status = h("p.nc-muted", { role: "status" });
const stage = h("div.nc-ar__stage", {});
const panel = h("div.nc-ar__panel", { "aria-live": "polite" });
stage.append(panel);
const modeSwitch = h("fieldset.nc-segmented", {}, h("legend.nc-label", {}, "Show"),
  h("div.nc-segmented__options", {}, [["week", "This week"], ["graph", "Zine map"]].map(([v, t]) =>
    h("label.nc-segmented__option", {}, h("input", { type: "radio", name: "mode", value: v, checked: v === mode }), h("span", {}, t)))));
const xrButtons = h("div.nc-cluster", {});
// The accessible twin of the scene: the same items as a list, in the same order.
const list = h("div.nc-stack", {});

const main = h("main.nc-container.nc-page.nc-ar", { id: "main", tabindex: "-1" },
  h("div.nc-stack", {}, h("p.nc-eyebrow", {}, "Preview"), h("h1.nc-h1", {}, "NightCal in 3D"),
    h("p.nc-lede", {}, "The same week and the same zine map, as things you can walk around. Drag to look, scroll to move closer, select a card to open it. On a phone or headset that supports it, you can place it in the room.")),
  h("div.nc-ar__bar", {}, modeSwitch, xrButtons),
  status, stage,
  h("section", { "aria-labelledby": "ar-list" }, h("h2.nc-h3", { id: "ar-list" }, "Everything in the scene"), list),
);
app.replaceChildren(siteHeader(), main, siteFooter({ notes: model.notes, source: model.source }));

async function showEvent(id) {
  const { eventCard } = await import("../../components/event-card/event-card.js");
  const ev = model.eventsById.get(id);
  if (!ev) return;
  const close = button({ label: "Close", variant: "secondary", onClick: () => panel.replaceChildren() });
  panel.replaceChildren(h("div.nc-stack", {}, eventCard(ev, { venue: model.venuesById.get(ev.venueId), today: model.today, level: 2, showImage: false }), close));
}
async function showNode(id) {
  const { zineCard } = await import("../../components/zine-card/zine-card.js");
  const n = graph3.byId.get(id);
  if (!n) return;
  const close = button({ label: "Close", variant: "secondary", onClick: () => panel.replaceChildren() });
  panel.replaceChildren(h("div.nc-stack", {}, zineCard(n, { level: 2 }), close));
}

function drawList() {
  if (mode === "week") {
    list.replaceChildren(...week.days.filter(d => d.events.length).map(d => h("section.nc-stack", {}, h("h3", {}, d.long),
      h("ol.nc-day-agenda__list", { role: "list" }, d.events.map(e => h("li", {}, eventRow(e)))))));
  } else {
    list.replaceChildren(h("ul.nc-zine__cards", { role: "list" }, graph3.nodes.filter(n => n.html || n.type === "venue").map(n =>
      h("li", {}, button({ label: n.title, variant: "secondary", onClick: () => { scene3d?.select(n.id); showNode(n.id); } })))));
  }
}
list.addEventListener("nc-select", e => { if (e.detail.kind === "event") showEvent(e.detail.id); });

let scene3d = null;
function hasWebGL() {
  try { const c = document.createElement("canvas"); return !!(c.getContext("webgl2") || c.getContext("webgl")); } catch { return false; }
}

if (!hasWebGL()) {
  status.textContent = "This browser can't draw 3D, so here is the same content as a list. Everything is also on the 2D calendar and zine.";
  stage.hidden = true;
} else {
  status.textContent = "Loading the 3D scene…";
  try {
    const { createScene, xrSupport } = await import("../render3d/scene.js");
    scene3d = createScene(stage, {
      onSelect: d => {
        if (d.kind === "event") showEvent(d.id);
        else if (d.kind === "node") { scene3d.select(d.id); showNode(d.id); }
        else if (d.kind === "day") status.textContent = `${d.date}: select a card under it to open a show.`;
      },
    });
    scene3d.setWeek(week, firstNight);
    scene3d.setGraph(graph3);
    scene3d.setMode(mode);
    status.textContent = "";
    const xr = await xrSupport();
    if (xr.ar) xrButtons.append(button({ label: "Place in your room (AR)", variant: "primary", onClick: () => scene3d.startXR("immersive-ar", document.body).catch(err => { status.textContent = `AR did not start: ${err.message}`; }) }));
    if (xr.vr) xrButtons.append(button({ label: "Enter VR", variant: xr.ar ? "secondary" : "primary", onClick: () => scene3d.startXR("immersive-vr").catch(err => { status.textContent = `VR did not start: ${err.message}`; }) }));
    if (!xr.ar && !xr.vr) xrButtons.append(h("p.nc-muted", {}, "AR needs a phone or headset with WebXR (for example Chrome on Android). This screen shows the 3D preview."));
  } catch (err) {
    console.error(err);
    stage.hidden = true;
    status.textContent = "The 3D scene could not load, so here is the same content as a list.";
  }
}
modeSwitch.addEventListener("change", e => { mode = e.target.value; setParam("mode", mode === "graph" ? "graph" : ""); scene3d?.setMode(mode); panel.replaceChildren(); drawList(); });
drawList();
