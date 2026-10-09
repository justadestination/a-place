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
  const root = h("section.nc-portal", { "aria-label": "Paper-to-Screen Portal" });

  const caps = capabilities || { hasWebGL: false, hasWebXR: false, arSupported: false };

  // 1. Portal header
  const titleTag = level === 1 ? "h1.nc-portal__title" : "h2.nc-portal__title";
  const header = h("header.nc-portal__header", {},
    h("span.nc-portal__eyebrow", {}, "Umwelt Horizons · Physical-to-Digital Portal"),
    h(titleTag, {}, "Portal Dispatch"),
    h("p.nc-portal__subtitle", {}, `Scanning target: ${targetId || "Zine Directory"}`)
  );

  // 2. Capability & Status indicator
  let capabilityBanner = null;
  if (caps.arSupported) {
    capabilityBanner = h("div.nc-portal__banner.nc-portal__banner--ar", {},
      h("span.nc-portal__badge", {}, "AR Layer Available"),
      h("p.nc-portal__banner-text", {}, "This device supports spatial AR. You can project this zine node into your room."),
      button({
        label: "Launch AR Spatial Portal",
        variant: "primary",
        onclick: () => {
          emit(root, "nc-portal-ar", { target: targetId });
        }
      })
    );
  } else {
    capabilityBanner = h("div.nc-portal__banner.nc-portal__banner--fallback", {},
      h("span.nc-portal__badge", {}, "Digital Reader Mode"),
      h("p.nc-portal__banner-text", {}, "Showing complete digital dispatch and graph links. Graceful non-AR reader view.")
    );
  }

  // 3. Target content resolution
  const contentHolder = h("div.nc-portal__content", {});
  const nodeTitleTag = level === 1 ? "h2.nc-portal__node-title" : "h3.nc-portal__node-title";

  if (nodeData) {
    const isNote = nodeData.type === "article" || nodeData.type === "review" || nodeData.type === "editorial" || nodeData.type === "letter";
    const titleEl = h(nodeTitleTag, {}, nodeData.title || targetId);
    const metaEl = h("p.nc-portal__node-meta", {},
      `${(nodeData.type || "dispatch").toUpperCase()} · ${(nodeData.author || "Umwelt Contributor")} · ${nodeData.date || "2026"}`
    );

    const bodyEl = h("div.nc-portal__node-body", {});
    if (nodeData.html) {
      bodyEl.innerHTML = nodeData.html;
    } else {
      bodyEl.textContent = nodeData.summary || "Full dispatch text available in zine graph.";
    }

    const navActions = h("div.nc-portal__actions", {},
      button({
        label: "View in Zine Node Map",
        variant: "secondary",
        href: `/zine/?node=${encodeURIComponent(targetId)}`,
      }),
      button({
        label: "Explore Calendar",
        variant: "ghost",
        href: "/",
      })
    );

    contentHolder.append(titleEl, metaEl, bodyEl, navActions);
  } else {
    // Default fallback presentation when target data is pending or mock
    contentHolder.append(
      h(nodeTitleTag, {}, `Bridged Content: ${targetId}`),
      h("p.nc-portal__node-meta", {}, "Physical zine marker acquired. Opening live graph context."),
      h("p.nc-portal__node-body", {}, "This portal links directly from printed paper into the live nightlife graph."),
      h("div.nc-portal__actions", {},
        button({ label: "Open Zine", variant: "primary", href: "/zine/" }),
        button({ label: "View Calendar", variant: "secondary", href: "/" })
      )
    );
  }

  root.append(header, capabilityBanner, contentHolder);
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
