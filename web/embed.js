/*! NightCal embed loader. Put this on any page:
 *
 *   <div data-nightcal="calendar-week" data-params="scope=nights" data-theme='{"scheme":"dark"}'></div>
 *   <script src="https://nightcal.justadestination.com/embed.js" async></script>
 *
 * Each element becomes a lazy-loaded, auto-sizing iframe of /embed/<name>/.
 * The iframe fires DOM events on the element:
 *   nightcal:ready, nightcal:select (detail: { kind, id, url, label }), nightcal:themechange
 * and the element gains .nightcal = { theme(spec), textScale(n), density(d), scheme(s) }.
 * No cookies, no tracking, nothing but postMessage between the two windows.
 */
(function () {
  var script = document.currentScript;
  var origin = script ? new URL(script.src).origin : "https://nightcal.justadestination.com";
  var frames = {};
  var n = 0;

  function mount(el) {
    if (el.__nightcal) return;
    var name = el.getAttribute("data-nightcal");
    if (!/^[a-z0-9-]+$/.test(name || "")) return;
    var id = "ncf" + (++n);
    var query = new URLSearchParams(el.getAttribute("data-params") || "");
    query.set("frameId", id);
    var theme = null;
    try { theme = JSON.parse(el.getAttribute("data-theme") || "null"); } catch (e) {}
    if (theme && theme.scheme) query.set("scheme", theme.scheme);
    if (theme && theme.textScale) query.set("textScale", theme.textScale);
    if (theme && theme.density) query.set("density", theme.density);
    var frame = document.createElement("iframe");
    frame.src = origin + "/embed/" + name + "/?" + query.toString();
    frame.title = el.getAttribute("data-title") || "NightCal: " + name.replace(/-/g, " ");
    frame.loading = "lazy";
    frame.style.cssText = "display:block;width:100%;border:0;height:" + (el.getAttribute("data-height") || "320") + "px";
    el.appendChild(frame);
    var send = function (msg) { msg.target = "nightcal"; frame.contentWindow && frame.contentWindow.postMessage(msg, origin); };
    el.__nightcal = true;
    el.nightcal = {
      theme: function (spec) { send({ type: "theme", spec: spec }); },
      textScale: function (v) { send({ type: "textScale", value: v }); },
      density: function (v) { send({ type: "density", value: v }); },
      scheme: function (v) { send({ type: "scheme", value: v }); },
    };
    frames[id] = { el: el, frame: frame, theme: theme };
  }

  window.addEventListener("message", function (event) {
    var msg = event.data;
    if (event.origin !== origin || !msg || msg.source !== "nightcal" || !frames[msg.frameId]) return;
    var f = frames[msg.frameId];
    if (event.source !== f.frame.contentWindow) return;
    if (msg.type === "resize" && msg.height > 0) f.frame.style.height = Math.ceil(msg.height) + "px";
    if (msg.type === "ready" && f.theme && Object.keys(f.theme).some(function (k) { return k !== "scheme" && k !== "textScale" && k !== "density"; })) f.el.nightcal.theme(f.theme);
    f.el.dispatchEvent(new CustomEvent("nightcal:" + msg.type, { detail: msg, bubbles: true }));
  });

  function scan() { Array.prototype.forEach.call(document.querySelectorAll("[data-nightcal]"), mount); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scan); else scan();
  window.NightCalEmbed = { scan: scan };
})();
