// NightCal theme API. Documented in docs/THEME_API.md.
//
// A theme is a JSON spec of token overrides plus four runtime knobs:
//   { version: 1, name, scheme, textScale, density, motion, tokens: {...}, schemes: { light: {...}, dark: {...} } }
// apply() validates it, refuses overrides that would drop any pair in
// tokens/pairs.json below WCAG AA, writes one <style> element, saves it, and
// fires "nightcal:themechange" on document. Nothing reloads.

import TOKENS from "./tokens.js";

const KEY = "nightcal.theme.v1";
const STYLE_ID = "nc-theme-overrides";
const P = TOKENS.prefix;
const SCHEMES = ["light", "dark"];
const DENSITIES = TOKENS.density;
const TEXT_SCALE = { min: 1, max: 2 };
const DENSITY_RANGE = { min: 0.75, max: 1.5 };

const root = () => document.documentElement;
const listeners = new Set();

/** Every token name an override may set ("color-accent", "radius-md"). Dots are accepted as separators too. */
export function tokenNames() {
  const names = new Set([...Object.keys(TOKENS.primitives), ...Object.keys(TOKENS.themes.light.values)]);
  return [...names].sort();
}

function toVar(key) { return P + String(key).replace(/\./g, "-"); }
function fromVar(name) { return name.replace(/\./g, "-"); }
const KNOWN = new Set([...Object.keys(TOKENS.primitives), ...Object.keys(TOKENS.themes.light.values)]);

// --- color parsing & contrast ----------------------------------------------

let ctx = null;
function rgba(value) {
  if (typeof value !== "string") return null;
  ctx = ctx || document.createElement("canvas").getContext("2d");
  ctx.fillStyle = "#010203";
  ctx.fillStyle = value;
  const out = ctx.fillStyle;
  if (out === "#010203" && value.trim().toLowerCase() !== "#010203") return null;
  if (out.startsWith("#")) return [1, 3, 5].map(i => parseInt(out.slice(i, i + 2), 16)).concat(1);
  const m = out.match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  const p = m[1].split(",").map(Number);
  return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
}
function lum([r, g, b]) {
  const c = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * c(r) + 0.7152 * c(g) + 0.0722 * c(b);
}
export function contrast(fg, bg) {
  const b = rgba(bg), f0 = rgba(fg);
  if (!b || !f0) return 0;
  const a = f0[3];
  const f = [0, 1, 2].map(i => f0[i] * a + b[i] * (1 - a));
  const [hi, lo] = [lum(f), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** Resolved value of a semantic or primitive token for one scheme, given overrides. */
function resolveIn(scheme, name, overrides) {
  if (name in overrides) return overrides[name];
  const theme = TOKENS.themes[scheme];
  const ref = theme.refs[name];
  if (ref) return overrides[ref] ?? TOKENS.primitives[ref];
  return theme.values[name] ?? TOKENS.primitives[name];
}

function pairFailures(scheme, overrides) {
  const out = [];
  for (const p of TOKENS.pairs) {
    const fg = resolveIn(scheme, "color-" + p.fg, overrides);
    const bg = resolveIn(scheme, "color-" + p.bg, overrides);
    const ratio = contrast(fg, bg);
    if (ratio + 1e-9 < p.min) out.push({ scheme, fg: p.fg, bg: p.bg, ratio: +ratio.toFixed(2), min: p.min });
  }
  return out;
}

// Which override keys feed a semantic name in a scheme (directly or via its primitive).
function feeders(scheme, semantic, overrides) {
  const keys = [];
  if (semantic in overrides) keys.push(semantic);
  const ref = TOKENS.themes[scheme].refs[semantic];
  if (ref && ref in overrides) keys.push(ref);
  return keys;
}

// --- spec -------------------------------------------------------------------

/** Normalise and validate a spec. Returns { spec, errors } and never throws. */
export function validate(input) {
  const errors = [];
  const spec = { version: 1 };
  if (!input || typeof input !== "object") return { spec, errors: ["spec must be an object"] };
  if (input.name != null) spec.name = String(input.name).slice(0, 80);
  if (input.scheme != null) {
    if (["light", "dark", "system"].includes(input.scheme)) spec.scheme = input.scheme;
    else errors.push(`scheme must be light, dark or system, got ${JSON.stringify(input.scheme)}`);
  }
  if (input.textScale != null) {
    const n = Number(input.textScale);
    if (Number.isFinite(n)) spec.textScale = Math.min(TEXT_SCALE.max, Math.max(TEXT_SCALE.min, Math.round(n * 1000) / 1000));
    else errors.push("textScale must be a number");
    if (Number.isFinite(n) && (n < TEXT_SCALE.min || n > TEXT_SCALE.max)) errors.push(`textScale clamped to ${spec.textScale} (allowed ${TEXT_SCALE.min}–${TEXT_SCALE.max})`);
  }
  if (input.density != null) {
    if (typeof input.density === "string" && input.density in DENSITIES) spec.density = input.density;
    else if (Number.isFinite(Number(input.density))) spec.density = Math.min(DENSITY_RANGE.max, Math.max(DENSITY_RANGE.min, Number(input.density)));
    else errors.push(`density must be ${Object.keys(DENSITIES).join(", ")} or a number`);
  }
  if (input.motion != null) {
    if (["system", "reduce", "full"].includes(input.motion)) spec.motion = input.motion;
    else errors.push("motion must be system, reduce or full");
  }
  const tokens = cleanTokens(input.tokens, "tokens", errors);
  if (Object.keys(tokens).length) spec.tokens = tokens;
  if (input.schemes && typeof input.schemes === "object") {
    for (const s of SCHEMES) {
      const t = cleanTokens(input.schemes[s], `schemes.${s}`, errors);
      if (Object.keys(t).length) (spec.schemes ||= {})[s] = t;
    }
  }
  return { spec, errors };
}

function cleanTokens(obj, where, errors) {
  const out = {};
  if (!obj) return out;
  if (typeof obj !== "object") { errors.push(`${where} must be an object`); return out; }
  for (const [key, value] of Object.entries(obj)) {
    const name = fromVar(key.startsWith(P) ? key.slice(P.length) : key);
    if (!KNOWN.has(name)) { errors.push(`${where}: unknown token "${key}"`); continue; }
    const v = String(value).trim();
    if (!v || /[;{}<>]|url\(|expression\(|@import/i.test(v)) { errors.push(`${where}: unsafe value for "${key}"`); continue; }
    if ((name.startsWith("color-") || name.startsWith("palette-")) && !rgba(v)) { errors.push(`${where}: "${key}" is not a color`); continue; }
    out[name] = v;
  }
  return out;
}

// Override selectors out-rank the base theme blocks in tokens.css
// (base max specificity 0,2,0; generic overrides 0,2,1; per-scheme 0,3,1).
function compileCss(spec) {
  const decl = obj => Object.entries(obj || {}).map(([k, v]) => `${P}${k}: ${v};`).join(" ");
  const parts = [];
  if (spec.tokens && Object.keys(spec.tokens).length) parts.push(`html:root:root { ${decl(spec.tokens)} }`);
  for (const s of SCHEMES) {
    const t = spec.schemes?.[s];
    if (!t || !Object.keys(t).length) continue;
    const other = s === "light" ? "dark" : "light";
    parts.push(`html:root:root[data-theme="${s}"] { ${decl(t)} }`);
    parts.push(`@media (prefers-color-scheme: ${s}) { html:root:root:not([data-theme="${other}"]) { ${decl(t)} } }`);
  }
  return parts.join("\n");
}

// --- state ------------------------------------------------------------------

let current = load() || { version: 1 };

function load() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(KEY) || "null"); } catch { saved = null; }
  // Embeds can be themed by query string (same keys the boot script reads).
  const q = new URLSearchParams(location.search);
  const fromQuery = {};
  if (q.get("scheme")) fromQuery.scheme = q.get("scheme");
  if (q.get("textScale")) fromQuery.textScale = Number(q.get("textScale"));
  if (q.get("density")) fromQuery.density = q.get("density");
  const merged = { ...(saved || {}), ...fromQuery };
  return Object.keys(merged).length ? validate(merged).spec : null;
}
function save(spec, css) {
  try { localStorage.setItem(KEY, JSON.stringify({ ...spec, css })); } catch { /* storage may be blocked; theme still applies for this page */ }
}

function paint(spec, css) {
  const d = root();
  d.toggleAttribute("data-theme", false);
  if (spec.scheme === "light" || spec.scheme === "dark") d.setAttribute("data-theme", spec.scheme);
  d.style.setProperty(`${P}text-scale`, String(spec.textScale ?? 1));
  d.removeAttribute("data-density");
  d.style.removeProperty(`${P}density`);
  if (typeof spec.density === "number") d.style.setProperty(`${P}density`, String(spec.density));
  else if (spec.density && spec.density !== "comfortable") d.setAttribute("data-density", spec.density);
  d.removeAttribute("data-motion");
  if (spec.motion === "reduce" || spec.motion === "full") d.setAttribute("data-motion", spec.motion);
  let el = document.getElementById(STYLE_ID);
  if (!css) { el?.remove(); return; }
  if (!el) { el = document.createElement("style"); el.id = STYLE_ID; document.head.append(el); }
  el.textContent = css;
}

/**
 * Apply a theme spec live. Options:
 *   merge (default true)   merge onto the current spec instead of replacing it
 *   persist (default true) save to localStorage so the next page boots with it
 *   enforceContrast (default true) drop overrides that break a pair in tokens/pairs.json
 * Returns { spec, errors, rejected, failures }.
 */
export function apply(input, { merge = true, persist = true, enforceContrast = true } = {}) {
  const { spec: incoming, errors } = validate(input);
  const spec = merge ? mergeSpecs(current, incoming) : incoming;
  const rejected = [];
  let failures = [];
  for (const scheme of SCHEMES) {
    for (;;) {
      const overrides = { ...(spec.tokens || {}), ...(spec.schemes?.[scheme] || {}) };
      const fails = pairFailures(scheme, overrides);
      if (!fails.length || !enforceContrast) { failures = failures.concat(fails); break; }
      // Drop the overrides behind the first failing pair, then re-check.
      const f = fails[0];
      const keys = [...feeders(scheme, "color-" + f.fg, overrides), ...feeders(scheme, "color-" + f.bg, overrides)];
      if (!keys.length) { failures = failures.concat(fails); break; }
      for (const k of keys) {
        rejected.push({ token: k, scheme, reason: `${f.fg} on ${f.bg} would be ${f.ratio}:1, needs ${f.min}:1` });
        if (spec.tokens) delete spec.tokens[k];
        if (spec.schemes?.[scheme]) delete spec.schemes[scheme][k];
      }
    }
  }
  const css = compileCss(spec);
  current = spec;
  paint(spec, css);
  if (persist) save(spec, css);
  const result = { spec: structuredClone(spec), errors, rejected, failures };
  document.dispatchEvent(new CustomEvent("nightcal:themechange", { detail: result }));
  listeners.forEach(fn => { try { fn(result); } catch (e) { console.error(e); } });
  return result;
}

function mergeSpecs(a, b) {
  const out = { ...a, ...b, version: 1 };
  if (a.tokens || b.tokens) out.tokens = { ...(a.tokens || {}), ...(b.tokens || {}) };
  if (a.schemes || b.schemes) {
    out.schemes = {};
    for (const s of SCHEMES) if (a.schemes?.[s] || b.schemes?.[s]) out.schemes[s] = { ...(a.schemes?.[s] || {}), ...(b.schemes?.[s] || {}) };
  }
  return structuredClone(out);
}

export const get = () => structuredClone(current);
export const reset = () => apply({ version: 1 }, { merge: false });
export const setTextScale = n => apply({ textScale: n });
export const setDensity = d => apply({ density: d });
export const setScheme = s => apply({ scheme: s });
export const setMotion = m => apply({ motion: m });
export const setToken = (key, value, scheme) => apply(scheme ? { schemes: { [scheme]: { [key]: value } } } : { tokens: { [key]: value } });
export function subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }

/** The scheme actually showing right now ("light" or "dark"). */
export function activeScheme() {
  const t = root().getAttribute("data-theme");
  if (t === "light" || t === "dark") return t;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Computed value of a token as the page sees it now (for canvas/WebGL renderers). */
export function read(key) {
  return getComputedStyle(root()).getPropertyValue(toVar(key)).trim();
}

/** True when motion should be skipped (system setting or the motion knob). */
export function reducedMotion() {
  const m = root().getAttribute("data-motion");
  if (m === "reduce") return true;
  if (m === "full") return false;
  return matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// Re-announce on system scheme flips so canvas/3D renderers can repaint.
matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => {
  document.dispatchEvent(new CustomEvent("nightcal:themechange", { detail: { spec: get(), errors: [], rejected: [], failures: [], system: true } }));
});

export const Theme = { apply, validate, get, reset, setTextScale, setDensity, setScheme, setMotion, setToken, subscribe, tokenNames, activeScheme, read, reducedMotion, contrast };
if (typeof window !== "undefined") {
  window.NightCal = window.NightCal || {};
  window.NightCal.theme = Theme;
}
export default Theme;
