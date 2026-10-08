// "/system/" — the living design system: tokens (read from the generated
// module, so it can never drift), components with their live embed routes,
// the embed snippet, and a theme API playground.
import { h } from "../core/dom.js";
import Theme from "../core/theme.js";
import TOKENS from "../core/tokens.js";
import { SITE } from "../core/site.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";
import { button } from "../../components/button/button.js";

const app = document.getElementById("app");
const registry = await fetch("/components/index.json").then(r => r.json()).catch(() => []);
const P = TOKENS.prefix;

const EXAMPLES = {
  "Larger text, roomy": { textScale: 1.5, density: "spacious" },
  "Night owl (dark, warm accent)": { scheme: "dark", schemes: { dark: { "color.accent": "#FF9E5E", "color.accent-text": "#FFB98C" } } },
  "High contrast light": { scheme: "light", schemes: { light: { "color.text-muted": "#2A2825", "color.border": "#57534A", "color.border-strong": "#121214" } } },
  "Breaks AA (watch it get refused)": { tokens: { "color.text-muted": "#CCCCCC" } },
};

const section = (id, title, ...children) => h("section", { id, "aria-labelledby": `${id}-h` }, h("h2.nc-h2", { id: `${id}-h` }, title), ...children);

function swatches() {
  const scheme = Theme.activeScheme();
  const names = Object.keys(TOKENS.themes[scheme].values).filter(n => n.startsWith("color-"));
  return h("ul.nc-swatches", { role: "list" }, names.map(n => {
    const value = Theme.read(n.replace(/-/g, ".")) || TOKENS.themes[scheme].values[n];
    return h("li.nc-swatch", {},
      h("span.nc-swatch__chip", { style: { background: `var(${P}${n})` }, "aria-hidden": "true" }),
      h("span", {}, h("code", {}, `${P}${n}`), h("small", {}, value)));
  }));
}

function typeScale() {
  const sizes = ["display", "3xl", "2xl", "xl", "lg", "md", "sm", "xs"];
  return h("div", {}, sizes.map(s => h("div.nc-type-row", {},
    h("code.nc-code", {}, `${P}font-size-${s} · ${TOKENS.primitives[`font-size-${s}`]}`),
    h("span", { style: { fontSize: `var(${P}font-size-${s})`, fontWeight: `var(${P}font-weight-${["md", "sm", "xs"].includes(s) ? "regular" : "heavy"})`, lineHeight: `var(${P}font-line-height-tight)` } }, "Turn of the Century, 9:00 pm"))));
}

function spacing() {
  return h("div.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-2)" } }, Object.keys(TOKENS.primitives).filter(k => /^space-\d$/.test(k) && k !== "space-0").map(k =>
    h("div.nc-space-row", {}, h("code.nc-code", { style: { minWidth: "min(100%, 9rem)" } }, `${P}${k}`), h("span.nc-space-row__bar", { style: { width: `var(${P}${k})` } }))));
}

function componentBlock(c) {
  const src = `/embed/${c.name}/`;
  const frame = h("iframe", { src, title: `${c.title} preview`, loading: "lazy", height: "200" });
  window.addEventListener("message", e => { if (e.source === frame.contentWindow && e.data?.type === "resize") frame.height = String(Math.min(900, e.data.height)); });
  const snippet = `<div data-nightcal="${c.name}"></div>\n<script src="${SITE.origin}/embed.js" async></script>`;
  return h("article.nc-comp", { id: `c-${c.name}`, "aria-labelledby": `c-${c.name}-h` },
    h("div.nc-comp__head", {}, h("h3", { id: `c-${c.name}-h` }, c.title), h("a.nc-link", { href: src }, `${src}`, h("span.nc-sr-only", {}, ` standalone route for ${c.title}`))),
    h("p", {}, c.summary),
    Object.keys(c.params || {}).length ? h("dl.nc-params", {}, Object.entries(c.params).map(([k, v]) => [h("dt", {}, k), h("dd", {}, v)])) : null,
    frame,
    h("details", {}, h("summary.nc-label", { style: { cursor: "pointer", minHeight: "var(--nc-size-target)", display: "flex", alignItems: "center" } }, `Embed code for ${c.title}`), h("pre.nc-pre", {}, snippet)),
  );
}

function playground() {
  const area = h("textarea.nc-textarea", { id: "spec", spellcheck: "false" }, JSON.stringify(Theme.get(), null, 2));
  const out = h("pre.nc-pre", { role: "status", "aria-live": "polite" }, "Result appears here.");
  const run = spec => {
    const r = Theme.apply(spec, { merge: false });
    area.value = JSON.stringify(r.spec, null, 2);
    out.textContent = JSON.stringify({ errors: r.errors, rejected: r.rejected, failures: r.failures }, null, 2);
    paintTokens();
  };
  return h("div.nc-stack", {},
    h("p", {}, "Paste or edit a theme spec and apply it. It changes this page live, with no reload, and is saved for your next visit. Overrides that would break WCAG AA contrast are refused and listed. The same call is what a Steward agent makes: ", h("code.nc-code", {}, "NightCal.theme.apply(spec)"), ". Full reference in docs/THEME_API.md."),
    h("div.nc-cluster", {}, Object.entries(EXAMPLES).map(([name, spec]) => button({ label: name, variant: "secondary", onClick: () => run(spec) }))),
    h("label.nc-label", { for: "spec" }, "Theme spec (JSON)"),
    area,
    h("div.nc-cluster", {},
      button({ label: "Apply", variant: "primary", onClick: () => { try { run(JSON.parse(area.value)); } catch (err) { out.textContent = `Not valid JSON: ${err.message}`; } } }),
      button({ label: "Reset to default", variant: "secondary", onClick: () => { Theme.reset(); area.value = JSON.stringify(Theme.get(), null, 2); out.textContent = "Reset."; paintTokens(); } })),
    h("h3.nc-h3", {}, "Result"),
    out,
  );
}

const colorSlot = h("div", {});
function paintTokens() { colorSlot.replaceChildren(swatches()); }

const embedDoc = h("div.nc-stack", {},
  h("p", {}, "Every component above has a standalone route at /embed/<name>/ with no page chrome. Drop it into any page with the loader, which lazy-loads an iframe, sizes it to its content, and passes your theme in:"),
  h("pre.nc-pre", {}, `<div data-nightcal="calendar-week"\n     data-params="scope=nights"\n     data-theme='{"scheme":"dark","textScale":1.25}'></div>\n<script src="${SITE.origin}/embed.js" async></script>\n\n<script>\n  document.querySelector("[data-nightcal]")\n    .addEventListener("nightcal:select", e => console.log(e.detail)); // { kind, id, url, label }\n</script>`),
  h("p", {}, "Or use a bare iframe and talk to it with postMessage. The frame sends ready, resize, select and themechange; it accepts theme, textScale, density, scheme and ping. See docs/THEME_API.md#embeds."),
);

const main = h("main.nc-container.nc-page.nc-gallery", { id: "main", tabindex: "-1" },
  h("div.nc-stack", {}, h("p.nc-eyebrow", {}, SITE.name), h("h1.nc-h1", {}, "Design system"),
    h("p.nc-lede", {}, "Every visual decision is a token. A theme is a set of token overrides. Every component has its own embed route. This page is generated from the same sources the site uses.")),
  h("nav.nc-gallery__nav", { "aria-label": "On this page" }, h("ul", { role: "list" },
    [["colors", "Colour"], ["type", "Type"], ["space", "Spacing"], ["components", "Components"], ["embeds", "Embeds"], ["theme-api", "Theme API"]].map(([id, t]) => h("li", {}, h("a", { href: `#${id}` }, t))))),
  section("colors", "Colour tokens", h("p", {}, `Showing the ${Theme.activeScheme()} theme as it is right now, including any overrides. Switch theme under Display to compare. Every pairing components use passes WCAG 2.2 AA in both themes; the build fails otherwise (tokens/pairs.json).`), colorSlot),
  section("type", "Type scale", h("p", {}, "System fonts only: nothing to download, nothing to flash. Sizes are rem, so the reader's browser setting and the text-size knob both scale everything."), typeScale()),
  section("space", "Spacing", h("p", {}, `Spacing multiplies by ${P}density (Tight 0.8, Normal 1, Roomy 1.25). Touch targets never shrink below ${TOKENS.primitives["size-target"]} (44px).`), spacing()),
  section("components", `Components (${registry.length})`, h("div.nc-stack", {}, registry.map(componentBlock))),
  section("embeds", "Embeds", embedDoc),
  section("theme-api", "Theme API playground", playground()),
);
app.replaceChildren(siteHeader(), main, siteFooter({}));
paintTokens();
document.addEventListener("nightcal:themechange", paintTokens);
if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView();
