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

let activeScene = null;

async function launchSpatialEngine(target, mode = "auto") {
  const statusEl = document.getElementById("portal-status");
  const stageEl = document.getElementById("portal-stage");

  if (!stageEl) return;
  stageEl.style.display = "block";
  stageEl.scrollIntoView({ behavior: "smooth", block: "nearest" });

  if (statusEl) {
    statusEl.style.display = "block";
    statusEl.textContent = "Loading 3D Spatial Engine & Umwelt graph...";
  }

  try {
    const { createScene, xrSupport } = await import("../render3d/scene.js");
    const { graphScene } = await import("../data/graph.js");
    const graph3 = graphScene(zine, { dims: 3 });

    // Clean previous scene
    if (activeScene) {
      try { activeScene.dispose(); } catch (_) {}
      activeScene = null;
    }
    stageEl.replaceChildren();

    activeScene = createScene(stageEl, {
      onSelect: d => {
        if (d.kind === "node" && statusEl) {
          const n = graph3.byId.get(d.id);
          statusEl.textContent = `Selected Umwelt node: ${n?.title || d.id}`;
        }
      }
    });

    activeScene.setGraph(graph3);
    activeScene.setMode("graph");
    activeScene.select(target);

    const xr = await xrSupport();

    if (xr.ar && mode !== "3d") {
      if (statusEl) statusEl.textContent = "Entering WebXR Spatial AR... Place the zine card in your room.";
      try {
        await activeScene.startXR("immersive-ar", document.body);
        if (statusEl) statusEl.textContent = "Spatial AR active. Umwelt dispatch placed in your environment.";
      } catch (xrErr) {
        console.warn("WebXR AR session did not start:", xrErr);
        if (statusEl) {
          statusEl.textContent = `AR camera note: ${xrErr.message || "Session ended"}. Interactive 3D spatial canvas active below.`;
        }
      }
    } else {
      if (statusEl) {
        statusEl.textContent = "Interactive 3D Spatial Canvas active. Drag to orbit, scroll or pinch to zoom.";
      }
    }
  } catch (err) {
    console.error("Failed to load 3D scene:", err);
    if (statusEl) {
      statusEl.textContent = "Could not initialize 3D scene: " + (err.message || String(err));
    }
  }
}

// Wire the AR/3D event listener
view.addEventListener("nc-portal-ar", (e) => {
  launchSpatialEngine(e.detail.target, e.detail.mode);
});

const main = h("main.nc-container.nc-page", { id: "main", tabindex: "-1" }, view);
app.replaceChildren(siteHeader(), main, siteFooter());
