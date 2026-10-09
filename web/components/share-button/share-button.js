import { h } from "../../js/core/dom.js";
import { intents, canNativeShare, nativeShare, copy, shareUrl } from "../../js/core/share.js";
import { button } from "../button/button.js";

const icon = () => {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true"); s.setAttribute("fill", "none");
  s.setAttribute("stroke", "currentColor"); s.setAttribute("stroke-width", "2"); s.setAttribute("stroke-linecap", "round");
  s.innerHTML = '<path d="M12 3v12M7 8l5-5 5 5M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/>';
  return s;
};

let uid = 0;

/**
 * Share control. Opens the device share sheet when there is one; otherwise a
 * small disclosure menu of share intents plus "Copy link".
 *   data: { title, text, url }   url defaults to the current page
 */
export function shareButton({ title = document.title, text = "", url, label = "Share", variant = "secondary" } = {}) {
  const id = `nc-share-${++uid}`;
  const data = () => ({ title, text, url: url || shareUrl() });
  const status = h("span.nc-sr-only", { role: "status" });
  const menu = h("div.nc-share__menu", { id, hidden: true });
  const wrap = h("div.nc-share", {});
  const trigger = button({
    label, variant, icon: icon(),
    attrs: { "aria-expanded": "false", "aria-controls": id },
    onClick: async () => {
      if (canNativeShare() && (await nativeShare(data()))) return;
      toggle(menu.hidden);
    },
  });

  function fill() {
    const d = data();
    menu.replaceChildren(
      h("ul.nc-share__list", { role: "list" },
        h("li", {}, h("button.nc-share__item", { type: "button", onclick: async () => {
          const ok = await copy(d.url);
          status.textContent = ok ? "Link copied." : "Could not copy. Select the address bar instead.";
          toggle(false); trigger.focus();
        } }, "Copy link")),
        intents(d).map(i => h("li", {}, h("a.nc-share__item", { href: i.href, target: "_blank", rel: "noopener" }, i.label, h("span.nc-sr-only", {}, " (opens in a new tab)")))),
      ),
    );
  }
  function toggle(open) {
    if (open) fill();
    menu.hidden = !open;
    trigger.setAttribute("aria-expanded", String(open));
    if (open) menu.querySelector("button, a")?.focus();
  }
  wrap.addEventListener("keydown", e => { if (e.key === "Escape" && !menu.hidden) { toggle(false); trigger.focus(); } });
  document.addEventListener("click", e => { if (!wrap.contains(e.target) && !menu.hidden) toggle(false); });
  wrap.append(trigger, menu, status);
  return wrap;
}

export const meta = {
  name: "share-button",
  title: "Share button",
  summary: "Native share sheet when available; otherwise copy link, X, Bluesky, Facebook and email intents.",
  params: { url: "URL to share (defaults to the page)", title: "share title", text: "share text" },
};

export function embed(params) {
  return shareButton({ url: params.get("url") || undefined, title: params.get("title") || "NightCal", text: params.get("text") || "What's on downtown tonight" });
}
