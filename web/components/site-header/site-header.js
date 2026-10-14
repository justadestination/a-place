import { h, svg } from "../../js/core/dom.js";
import { button } from "../button/button.js";
import { themeControls } from "../theme-controls/theme-controls.js";
import { searchDialog, searchButton } from "../search-dialog/search-dialog.js";
import { getStewardDrawer, isStewardActive } from "../steward-drawer/steward-drawer.js";

const BRAND = "/assets/brand";

const SURFACES = [
  {
    id: "nightcal",
    href: "/",
    label: "NightCal",
    mark: `${BRAND}/nightcal-256.png`,
    accent: "var(--nc-color-accent, #E5A93C)",
    match: p => p === "/" || p.startsWith("/calendar") || p.startsWith("/today") || p.startsWith("/day") || p.startsWith("/road"),
  },
  {
    id: "umwelt",
    href: "/zine/",
    label: "Umwelt Horizons",
    mark: `${BRAND}/uh-crimson-256.png`,
    // Mark is deep crimson (#A51C30); label uses a lifted crimson so it stays legible on dark.
    accent: "#E0566B",
    match: p => p.startsWith("/zine") || p.startsWith("/portal"),
  },
  {
    id: "serendipilyst",
    href: "/market/",
    label: "SerendipiLyst",
    mark: `${BRAND}/serendipilyst-pedestal-256.png`,
    accent: "#68D391",
    match: p => p.startsWith("/market"),
  },
];

// ShadeNet portal mark treatments. Pick one with ?mark=gray|silver|blue (remembered per browser).
const SHADENET_MARKS = {
  gray: `${BRAND}/shadenet-gray-256.png`,
  silver: `${BRAND}/shadenet-silver-256.png`,
  blue: `${BRAND}/shadenet-blue-256.png`,
};
// Wordmark faces under trial. Pick with ?wordmark=syne|unbounded|righteous.
const WORDMARK_FONTS = ["syne", "unbounded", "righteous"];

function trialChoice(param, allowed, fallback) {
  if (typeof location === "undefined") return fallback;
  const key = `shadenet_${param}`;
  try {
    const fromUrl = new URLSearchParams(location.search).get(param);
    if (fromUrl && allowed.includes(fromUrl)) localStorage.setItem(key, fromUrl);
    const stored = localStorage.getItem(key);
    return allowed.includes(stored) ? stored : fallback;
  } catch {
    return fallback;
  }
}

const icon = (...children) => svg("svg", {
  viewBox: "0 0 24 24", "aria-hidden": "true", fill: "none",
  stroke: "currentColor", "stroke-width": "2", "stroke-linecap": "round",
}, ...children);

const gear = () => icon(
  svg("path", { d: "M4 7h10M18 7h2M4 17h4M12 17h8" }),
  svg("circle", { cx: "16", cy: "7", r: "2" }),
  svg("circle", { cx: "10", cy: "17", r: "2" }),
);

const stewardIcon = () => icon(
  svg("path", { d: "M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" }),
);

/**
 * Fixed, faint background watermark. Always the ShadeNet mark; the active
 * surface's mark joins it (e.g. ShadeNet + NightCal on the calendar).
 * Sits behind page content so opaque cards and buttons cover it.
 */
function mountWatermark(shadenetMark, surface) {
  if (typeof document === "undefined" || !document.body || document.body.classList.contains("nc-embed")) return;
  document.querySelector(".nc-watermark")?.remove();
  const marks = [h("img.nc-watermark__mark.nc-watermark__mark--shadenet", { src: shadenetMark, alt: "" })];
  if (surface) marks.push(h(`img.nc-watermark__mark.nc-watermark__mark--${surface.id}`, { src: surface.mark, alt: "" }));
  document.body.prepend(h("div.nc-watermark", { "aria-hidden": "true", "data-surface": surface?.id || "shadenet" }, ...marks));
}

/**
 * Site header, top to bottom:
 *   1. Search (left) · ShadeNet portal mark with wordmark over it (centre) · Display (right)
 *   2. Surfaces: NightCal · Umwelt Horizons · SerendipiLyst
 *   3. Steward, on its own line
 */
export function siteHeader({ path = (typeof location !== "undefined" ? location.pathname : "/") } = {}) {
  const drawer = typeof document !== "undefined" ? getStewardDrawer() : null;
  const markChoice = trialChoice("mark", Object.keys(SHADENET_MARKS), "gray");
  const fontChoice = trialChoice("wordmark", WORDMARK_FONTS, "syne");
  const activeSurface = SURFACES.find(s => s.match(path)) || null;
  mountWatermark(SHADENET_MARKS[markChoice], activeSurface);

  // --- Row 1: Search · ShadeNet portal · Display ---
  const panel = h("div.nc-site-header__panel", { id: "nc-display-panel", hidden: true }, themeControls());
  const toggle = button({
    label: "Display",
    variant: "ghost",
    icon: gear(),
    attrs: { "aria-expanded": "false", "aria-controls": "nc-display-panel" },
  });
  const set = open => {
    panel.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    if (open) panel.querySelector("input:checked, input")?.focus();
  };
  toggle.addEventListener("click", () => set(panel.hidden));
  panel.addEventListener("keydown", e => { if (e.key === "Escape") { set(false); toggle.focus(); } });
  if (typeof document !== "undefined") {
    document.addEventListener("click", e => {
      if (!panel.hidden && !panel.contains(e.target) && !toggle.contains(e.target)) set(false);
    });
  }

  const searchModal = searchDialog();
  if (typeof document !== "undefined" && document.body && !document.body.contains(searchModal)) {
    document.body.appendChild(searchModal);
  }
  const searchTrigger = searchButton(() => searchModal.open());
  searchTrigger.append(h("span.nc-site-header__tool-label", {}, "Search"));

  const shadenetBrand = h("a.nc-shadenet-brand", {
    href: "/",
    title: "ShadeNet Downtown Autonomous Network",
    "data-mark": markChoice,
    "data-font": fontChoice,
  },
    h("img.nc-shadenet-brand__logo", { src: SHADENET_MARKS[markChoice], alt: "", width: "112", height: "112" }),
    h("span.nc-shadenet-brand__text", {}, "ShadeNet")
  );

  const row1 = h("div.nc-site-header__row1", {},
    h("div.nc-site-header__left", {}, searchTrigger),
    h("div.nc-site-header__center", {}, shadenetBrand),
    h("div.nc-site-header__right", {}, toggle, panel)
  );

  // --- Row 2: Surfaces ---
  const surfaceItems = SURFACES.map(s => {
    const isActive = s === activeSurface;
    return h("li.nc-surface-nav__item", { key: s.id },
      h("a", {
        href: s.href,
        class: `nc-surface-nav__link nc-surface-nav__link--${s.id}${isActive ? " is-active" : " is-inactive"}`,
        "aria-current": isActive ? "page" : null,
        style: `--nc-surface-accent: ${s.accent};`,
      },
        h("img.nc-surface-nav__icon", { src: s.mark, alt: "", height: "40", "aria-hidden": "true" }),
        h("span.nc-surface-nav__label", {}, s.label)
      )
    );
  });
  const row2 = h("nav.nc-surface-nav", { "aria-label": "Network Surfaces" },
    h("ul.nc-surface-nav__list", { role: "list" }, ...surfaceItems)
  );

  // --- Row 3: Steward ---
  const stewardBtn = button({
    label: "Steward",
    variant: isStewardActive() ? "secondary" : "ghost",
    icon: stewardIcon(),
    attrs: {
      "aria-haspopup": "dialog",
      title: isStewardActive() ? "Personal Steward Active — View Cockpit" : "Activate Personal Steward",
    },
    onClick: (e) => {
      e.preventDefault();
      if (drawer) drawer.open();
    },
  });
  if (typeof window !== "undefined") {
    window.addEventListener("shadenet:stewardchange", e => {
      stewardBtn.className = `nc-button nc-button--${e.detail?.active ? "secondary" : "ghost"}`;
    });
  }
  const row3 = h("div.nc-site-header__steward", {}, stewardBtn);

  return h("header.nc-site-header", {},
    h("div.nc-container.nc-site-header__container", {}, row1, row2, row3)
  );
}

export const meta = {
  name: "site-header",
  title: "Site header",
  summary: "ShadeNet portal mark with Search and Display, the three surfaces (NightCal, Umwelt Horizons, SerendipiLyst), and the Steward entry point.",
  params: {},
};

export function embed() { return siteHeader({ path: "/" }); }
