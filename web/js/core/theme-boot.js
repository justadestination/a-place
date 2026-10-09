// Inlined into <head> of every page by tools/build_pages.py, before any CSS paints.
// Applies the saved theme (scheme, text scale, density, motion, token overrides)
// synchronously so a reload or a theme switch never flashes the wrong theme.
// Keep it tiny and dependency-free. The full API lives in theme.js.
(function () {
  var d = document.documentElement, s = null, q = null;
  try { s = JSON.parse(localStorage.getItem("nightcal.theme.v1") || "null"); } catch (e) {}
  try { q = new URLSearchParams(location.search); } catch (e) {}
  // Embeds may be themed by query (?scheme=dark&textScale=1.25&density=compact)
  // so the first paint inside an iframe already matches the host.
  if (q) {
    s = s || {};
    if (q.get("scheme")) s.scheme = q.get("scheme");
    if (q.get("textScale")) s.textScale = parseFloat(q.get("textScale"));
    if (q.get("density")) s.density = q.get("density");
  }
  if (!s) return;
  if (s.scheme === "light" || s.scheme === "dark") d.setAttribute("data-theme", s.scheme);
  if (s.textScale > 0) d.style.setProperty("--nc-text-scale", String(Math.min(2, Math.max(1, s.textScale))));
  if (typeof s.density === "number") d.style.setProperty("--nc-density", String(s.density));
  else if (s.density === "compact" || s.density === "spacious") d.setAttribute("data-density", s.density);
  if (s.motion === "reduce" || s.motion === "full") d.setAttribute("data-motion", s.motion);
  if (s.css) {
    var el = document.createElement("style");
    el.id = "nc-theme-overrides";
    el.textContent = s.css;
    document.head.appendChild(el);
  }
})();
