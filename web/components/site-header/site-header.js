import { h } from "../../js/core/dom.js";
import { SITE } from "../../js/core/site.js";
import { button } from "../button/button.js";
import { themeControls } from "../theme-controls/theme-controls.js";

const NAV = [
  { href: "/", label: "Calendar", match: p => p === "/" || p.startsWith("/calendar") },
  { href: "/zine/", label: "Zine", match: p => p.startsWith("/zine") },
];

const gear = () => {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true"); s.setAttribute("fill", "none");
  s.setAttribute("stroke", "currentColor"); s.setAttribute("stroke-width", "2"); s.setAttribute("stroke-linecap", "round");
  s.innerHTML = '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>';
  return s;
};

/**
 * Page chrome: wordmark, two destinations, and the Display settings disclosure.
 * Embeds never include it (except at /embed/site-header for preview).
 */
export function siteHeader({ path = location.pathname } = {}) {
  const panel = h("div.nc-site-header__panel", { id: "nc-display-panel", hidden: true }, themeControls());
  const toggle = button({ label: "Display", variant: "ghost", icon: gear(), attrs: { "aria-expanded": "false", "aria-controls": "nc-display-panel" } });
  const set = open => { panel.hidden = !open; toggle.setAttribute("aria-expanded", String(open)); if (open) panel.querySelector("input:checked, input")?.focus(); };
  toggle.addEventListener("click", () => set(panel.hidden));
  panel.addEventListener("keydown", e => { if (e.key === "Escape") { set(false); toggle.focus(); } });
  document.addEventListener("click", e => { if (!panel.hidden && !panel.contains(e.target) && !toggle.contains(e.target)) set(false); });

  return h("header.nc-site-header", {},
    h("div.nc-container.nc-site-header__inner", {},
      h("a.nc-wordmark", { href: "/" },
        h("span.nc-wordmark__name", {}, SITE.name),
        h("span.nc-wordmark__place", {}, SITE.place)),
      h("nav.nc-site-header__nav", { "aria-label": "Main" },
        h("ul", { role: "list" }, NAV.map(item => h("li", {}, h("a", { href: item.href, "aria-current": item.match(path) ? "page" : null }, item.label))))),
      h("div.nc-site-header__tools", {}, toggle, panel),
    ),
  );
}

export const meta = {
  name: "site-header",
  title: "Site header",
  summary: "Wordmark, Calendar and Zine links, and the Display settings disclosure. Page chrome only.",
  params: {},
};

export function embed() { return siteHeader({ path: "/" }); }
