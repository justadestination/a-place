import { h } from "../../js/core/dom.js";
import { SITE } from "../../js/core/site.js";
import { button } from "../button/button.js";
import { themeControls } from "../theme-controls/theme-controls.js";
import { searchDialog, searchButton } from "../search-dialog/search-dialog.js";
import { getStewardDrawer, isStewardActive } from "../steward-drawer/steward-drawer.js";

const SURFACES = [
  {
    id: "nightcal",
    href: "/",
    label: "NightCal",
    mark: "/assets/brand/nightcal-accent.png",
    accent: "var(--nc-color-accent, #E5A93C)",
    match: p => p === "/" || p.startsWith("/calendar") || p.startsWith("/today") || p.startsWith("/day"),
  },
  {
    id: "umwelt",
    href: "/zine/",
    label: "Umwelt Horizons",
    mark: "/assets/brand/uh-accent.png",
    accent: "#F4EEDC",
    match: p => p.startsWith("/zine") || p.startsWith("/portal"),
  },
  {
    id: "serendipilyst",
    href: "/market/",
    label: "Serendipilyst",
    mark: "/assets/brand/serendipilyst-accent.png",
    accent: "#C88A22",
    match: p => p.startsWith("/market"),
  },
];

const gear = () => {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true"); s.setAttribute("fill", "none");
  s.setAttribute("stroke", "currentColor"); s.setAttribute("stroke-width", "2"); s.setAttribute("stroke-linecap", "round");
  s.innerHTML = '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>';
  return s;
};

const stewardIcon = () => {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true"); s.setAttribute("fill", "none");
  s.setAttribute("stroke", "currentColor"); s.setAttribute("stroke-width", "2"); s.setAttribute("stroke-linecap", "round");
  s.innerHTML = '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>';
  return s;
};

const chatIcon = () => {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true"); s.setAttribute("fill", "none");
  s.setAttribute("stroke", "currentColor"); s.setAttribute("stroke-width", "2"); s.setAttribute("stroke-linecap", "round");
  s.innerHTML = '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>';
  return s;
};

/**
 * 2-Row Unified Site Header:
 *   Row 1: Centered Tri-Surface Navigation (NightCal · Umwelt Horizons · Serendipilyst)
 *          Active surface has inverted/high-contrast styling; inactive surfaces mirrored/subtle.
 *   Row 2: Search on Left · Centered ShadeNet Logo & Wordmark · Chat / Steward / Display on Right.
 */
export function siteHeader({ path = (typeof location !== "undefined" ? location.pathname : "/") } = {}) {
  // Ensure Steward drawer exists in DOM
  let drawer = null;
  if (typeof document !== "undefined") {
    drawer = getStewardDrawer();
  }

  // --- Row 1: Surfaces Nav ---
  const surfaceItems = SURFACES.map(s => {
    const isActive = s.match(path);
    const cls = `nc-surface-nav__link nc-surface-nav__link--${s.id}${isActive ? " is-active" : " is-inactive"}`;

    return h("li.nc-surface-nav__item", { key: s.id },
      h("a", {
        href: s.href,
        class: cls,
        "aria-current": isActive ? "page" : null,
        style: `--nc-surface-accent: ${s.accent};`,
      },
        h("img.nc-surface-nav__icon", { src: s.mark, alt: "", width: "22", height: "22", "aria-hidden": "true" }),
        h("span.nc-surface-nav__label", {}, s.label)
      )
    );
  });

  const row1 = h("div.nc-site-header__row1", {},
    h("nav.nc-surface-nav", { "aria-label": "Network Surfaces" },
      h("ul.nc-surface-nav__list", { role: "list" }, ...surfaceItems)
    )
  );

  // --- Row 2: ShadeNet Core & Tools ---
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

  // Search dialog
  const searchModal = searchDialog();
  if (typeof document !== "undefined" && document.body && !document.body.contains(searchModal)) {
    document.body.appendChild(searchModal);
  }
  const searchTrigger = searchButton(() => searchModal.open());

  // Chat button
  const chatBtn = button({
    label: "Chat",
    variant: "ghost",
    href: "/chat/",
    icon: chatIcon(),
    attrs: { title: "Open Downtown Night Chat" },
  });

  // Steward button (opens cockpit/activation drawer)
  const stewardBtn = button({
    label: isStewardActive() ? "Steward" : "Steward",
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

  // Listen for steward state changes to update button styling
  if (typeof window !== "undefined") {
    window.addEventListener("shadenet:stewardchange", e => {
      const active = e.detail?.active;
      stewardBtn.className = `nc-button nc-button--${active ? "secondary" : "ghost"}`;
    });
  }

  // ShadeNet Umbrella Brand Anchor (Center)
  const shadenetBrand = h("a.nc-shadenet-brand", { href: "/", title: "ShadeNet Downtown Autonomous Network" },
    h("img.nc-shadenet-brand__logo", { src: "/assets/brand/shadenet-accent.png", alt: "", width: "32", height: "32" }),
    h("span.nc-shadenet-brand__text", {}, "ShadeNet")
  );

  const row2 = h("div.nc-site-header__row2", {},
    h("div.nc-site-header__left", {}, searchTrigger),
    h("div.nc-site-header__center", {}, shadenetBrand),
    h("div.nc-site-header__right", {},
      chatBtn,
      stewardBtn,
      toggle,
      panel
    )
  );

  return h("header.nc-site-header", {},
    h("div.nc-container.nc-site-header__container", {},
      row1,
      row2
    )
  );
}

export const meta = {
  name: "site-header",
  title: "Site header",
  summary: "Tri-surface top nav (NightCal, Umwelt Horizons, Serendipilyst) and ShadeNet core toolbar.",
  params: {},
};

export function embed() { return siteHeader({ path: "/" }); }
