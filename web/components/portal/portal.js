import { h, emit } from "../../js/core/dom.js";
import { button } from "../button/button.js";

/**
 * Probe device capabilities: WebGL & WebXR (immersive-ar)
 */
export async function probeCapabilities() {
  let hasWebGL = false;
  try {
    const canvas = document.createElement("canvas");
    hasWebGL = !!(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    hasWebGL = false;
  }

  let hasWebXR = false;
  let arSupported = false;
  if (typeof navigator !== "undefined" && navigator.xr && typeof navigator.xr.isSessionSupported === "function") {
    hasWebXR = true;
    try {
      arSupported = await navigator.xr.isSessionSupported("immersive-ar");
    } catch {
      arSupported = false;
    }
  }

  return { hasWebGL, hasWebXR, arSupported };
}

/**
 * Render portal experience for print-to-screen bridge
 */
export function portalView({
  targetId = "note:the-room-after-midnight",
  arRequested = false,
  nodeData = null,
  capabilities = null,
  level = 1,
} = {}) {
  const root = h("section.nc-portal", { "aria-label": "Umwelt Paper-to-Screen Portal" });

  const caps = capabilities || { hasWebGL: false, hasWebXR: false, arSupported: false };

  // 1. Portal header
  const titleTag = level === 1 ? "h1.nc-portal__title" : "h2.nc-portal__title";
  const header = h("header.nc-portal__header", {},
    h("span.nc-portal__eyebrow", {},
      h("img", { src: "/assets/brand/uh-accent.png", alt: "", width: "20", height: "13", style: "vertical-align: middle; margin-inline-end: 6px; display: inline-block;" }),
      "Umwelt (The Zine) · Print-to-Screen Portal"
    ),
    h(titleTag, {}, "Umwelt Dispatch Portal"),
    h("p.nc-portal__subtitle", {}, `Target: ${nodeData?.title || targetId} · Umwelt Zine Archive`)
  );

  // 2. 3D Stage & Status container
  const stageEl = h("div.nc-portal__stage", { id: "portal-stage", style: "display: none;" });
  const statusEl = h("p.nc-portal__status", { id: "portal-status", role: "status", style: "display: none;" });

  // 3. Capability & Action banner
  let capabilityBanner = null;
  if (caps.arSupported) {
    const arBtn = button({
      label: "Launch AR Spatial Portal",
      variant: "primary",
      onClick: () => {
        emit(root, "nc-portal-ar", { target: targetId, mode: "ar" });
      }
    });
    arBtn.addEventListener("click", (e) => {
      e.preventDefault();
      emit(root, "nc-portal-ar", { target: targetId, mode: "ar" });
    });

    capabilityBanner = h("div.nc-portal__banner.nc-portal__banner--ar", {},
      h("span.nc-portal__badge", {}, "WebXR AR Ready"),
      h("p.nc-portal__banner-text", {}, "This device supports spatial AR. Click below to place this Umwelt zine node in your physical room."),
      h("div.nc-portal__actions", {}, arBtn)
    );
  } else {
    const spatialBtn = button({
      label: "Launch 3D Spatial Canvas",
      variant: "primary",
      onClick: () => {
        emit(root, "nc-portal-ar", { target: targetId, mode: "3d" });
      }
    });
    spatialBtn.addEventListener("click", (e) => {
      e.preventDefault();
      emit(root, "nc-portal-ar", { target: targetId, mode: "3d" });
    });

    capabilityBanner = h("div.nc-portal__banner.nc-portal__banner--fallback", {},
      h("span.nc-portal__badge", {}, "Spatial Reader Mode (WebGL)"),
      h("p.nc-portal__banner-text", {}, "Interactive 3D spatial canvas available. (Camera AR uses WebXR on supported mobile devices like Chrome on Android)."),
      h("div.nc-portal__actions", {},
        spatialBtn,
        button({
          label: "Full 3D Scene",
          variant: "secondary",
          href: `/3d/?mode=graph&node=${encodeURIComponent(targetId)}`
        })
      )
    );
  }

  // 4. Target content resolution
  const contentHolder = h("div.nc-portal__content", {});
  const nodeTitleTag = level === 1 ? "h2.nc-portal__node-title" : "h3.nc-portal__node-title";

  if (nodeData) {
    const titleEl = h(nodeTitleTag, {}, nodeData.title || targetId);
    const metaEl = h("p.nc-portal__node-meta", {},
      `UMWELT DISPATCH · ${(nodeData.type || "dispatch").toUpperCase()} · ${(nodeData.author || "Umwelt Contributor")} · ${nodeData.date || "2026"}`
    );

    const bodyEl = h("div.nc-portal__node-body", {});
    if (nodeData.html) {
      bodyEl.innerHTML = nodeData.html;
    } else {
      bodyEl.textContent = nodeData.summary || "Full dispatch text available in Umwelt zine graph.";
    }

    const navActions = h("div.nc-portal__actions", {},
      button({
        label: "View in Umwelt Node Map",
        variant: "secondary",
        href: `/zine/?node=${encodeURIComponent(targetId)}`,
      }),
      button({
        label: "Read Umwelt Zine",
        variant: "secondary",
        href: "/zine/",
      }),
      button({
        label: "NightCal Calendar",
        variant: "ghost",
        href: "/",
      })
    );

    contentHolder.append(titleEl, metaEl, bodyEl, navActions);
  } else {
    contentHolder.append(
      h(nodeTitleTag, {}, `Bridged Content: ${targetId}`),
      h("p.nc-portal__node-meta", {}, "Physical Umwelt zine marker acquired. Opening live graph context."),
      h("p.nc-portal__node-body", {}, "This portal links directly from printed paper into the live nightlife graph."),
      h("div.nc-portal__actions", {},
        button({ label: "Open Umwelt Zine", variant: "primary", href: "/zine/" }),
        button({ label: "View Calendar", variant: "secondary", href: "/" })
      )
    );
  }

  root.append(header, capabilityBanner, statusEl, stageEl, contentHolder);
  return root;
}

export const meta = {
  name: "portal",
  title: "Paper-to-screen portal",
  summary: "Zine paper-to-screen portal bridging physical print markers into AR spatial content or responsive reader fallback.",
  params: {
    target: "target node or entity ID (defaults to sample note)",
    ar: "1 to request AR mode"
  },
};

export async function embed(params) {
  const targetId = params.get("target") || "note:the-room-after-midnight";
  const arRequested = params.get("ar") === "1";
  const caps = await probeCapabilities();

  // Try loading real zine data if in browser
  let nodeData = null;
  try {
    const { loadZine } = await import("../../js/data/graph.js");
    const zine = await loadZine();
    nodeData = zine.nodes.find(n => n.id === targetId || n.slug === targetId);
  } catch {
    // Non-fatal fallback
  }

  return portalView({ targetId, arRequested, nodeData, capabilities: caps, level: 2 });
}
