import { h } from "../../js/core/dom.js";

/**
 * Button or link styled as a button.
 *   variant: "primary" (one per screen) | "secondary" | "ghost"
 *   href: renders <a>; external links open in a new tab and say so to screen readers
 */
export function button({ label, variant = "secondary", href, external, icon, onClick, type = "button", attrs = {}, hideLabel = false } = {}) {
  const cls = `nc-button nc-button--${variant}${hideLabel ? " nc-button--icon" : ""}`;
  const content = [icon || null, hideLabel ? h("span.nc-sr-only", {}, label) : h("span", {}, label)];
  if (external) content.push(h("span.nc-sr-only", {}, " (opens in a new tab)"));
  if (href) {
    return h("a", { class: cls, href, target: external ? "_blank" : null, rel: external ? "noopener" : null, ...attrs, onclick: onClick }, content);
  }
  return h("button", { class: cls, type, ...attrs, onclick: onClick, "aria-label": hideLabel ? null : attrs["aria-label"] }, content);
}

export const meta = {
  name: "button",
  title: "Button",
  summary: "The one control style. Primary is reserved for the single main action on a screen.",
  params: { label: "text", variant: "primary | secondary | ghost", href: "optional URL" },
};

export function embed(params) {
  const variant = params.get("variant");
  const variants = variant ? [variant] : ["primary", "secondary", "ghost"];
  return h("div.nc-cluster", {}, variants.map(v => button({ label: params.get("label") || `${v[0].toUpperCase()}${v.slice(1)} action`, variant: v, href: params.get("href") || undefined })));
}
