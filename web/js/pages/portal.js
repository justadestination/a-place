import { h, params } from "../core/dom.js";
import "../core/theme.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";
import { loadZine } from "../data/graph.js";
import { portalView, probeCapabilities } from "../../components/portal/portal.js";

const app = document.getElementById("app");
const q = params();
const targetId = q.get("target") || q.get("node") || "note:the-room-after-midnight";
const arRequested = q.get("ar") === "1";

const [caps, zine] = await Promise.all([
  probeCapabilities(),
  loadZine().catch(() => ({ nodes: [] })),
]);

const nodeData = zine.nodes.find(n => n.id === targetId || n.slug === targetId) || null;

const view = portalView({
  targetId,
  arRequested,
  nodeData,
  capabilities: caps,
});

const main = h("main.nc-container.nc-page", { id: "main", tabindex: "-1" }, view);

app.replaceChildren(siteHeader(), main, siteFooter());
