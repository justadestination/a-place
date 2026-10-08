// Embed bridge: lets a NightCal route live in an <iframe> on someone else's page.
// Protocol (documented in docs/THEME_API.md#embeds and web/README.md):
//
//   frame -> host   { source: "nightcal", version: 1, frameId, type, ... }
//     ready        { route }                        once, after first render
//     resize       { height }                       whenever content height changes
//     select       { kind, id, url, label }         reader activated an event/day/node
//     themechange  { spec }                         after a theme message was applied
//
//   host -> frame   { target: "nightcal", type, ... }
//     theme        { spec }        apply a theme spec (not persisted inside the frame)
//     textScale    { value }       1–2
//     density      { value }       "compact" | "comfortable" | "spacious" | number
//     scheme       { value }       "light" | "dark" | "system"
//     ping         {}              frame answers with "ready"
//
// Messages carry no personal data, so the frame posts to "*". Hosts should
// still check event.source === iframe.contentWindow.

import Theme from "./theme.js";

const framed = (() => { try { return window.self !== window.top; } catch { return true; } })();
const frameId = new URLSearchParams(location.search).get("frameId") || "";

export const isFramed = () => framed;

export function post(type, data = {}) {
  if (!framed) return;
  window.parent.postMessage({ source: "nightcal", version: 1, frameId, type, ...data }, "*");
}

/** Tell the host what the reader picked. Outside a frame this is a no-op. */
export function select(kind, id, extra = {}) { post("select", { kind, id, ...extra }); }

/** Start the bridge for an embed route. Call once after the first render. */
export function startEmbed(route) {
  document.body.classList.add("nc-embed");
  if (!framed) return;
  let last = 0;
  const report = () => {
    const height = Math.ceil(document.documentElement.getBoundingClientRect().height);
    if (Math.abs(height - last) > 1) { last = height; post("resize", { height }); }
  };
  new ResizeObserver(report).observe(document.documentElement);
  window.addEventListener("message", event => {
    const msg = event.data;
    if (!msg || msg.target !== "nightcal" || event.source !== window.parent) return;
    const opts = { persist: false };
    let result = null;
    if (msg.type === "theme") result = Theme.apply(msg.spec || {}, opts);
    else if (msg.type === "textScale") result = Theme.apply({ textScale: msg.value }, opts);
    else if (msg.type === "density") result = Theme.apply({ density: msg.value }, opts);
    else if (msg.type === "scheme") result = Theme.apply({ scheme: msg.value }, opts);
    else if (msg.type === "ping") post("ready", { route });
    if (result) post("themechange", { spec: result.spec, rejected: result.rejected, errors: result.errors });
  });
  post("ready", { route });
  report();
}
