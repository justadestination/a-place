// Tiny DOM helper. h("button.nc-button", {type: "button", onclick}, "Label")
// Attributes starting with "on" become listeners; null/false attributes are skipped;
// children may be strings, nodes, arrays, or null.

export function h(spec, attrs = {}, ...children) {
  const [tag, ...classes] = spec.split(".");
  const el = document.createElement(tag || "div");
  if (classes.length) el.className = classes.join(" ");
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
    else if (key === "class") el.className = [el.className, value].filter(Boolean).join(" ");
    else if (key === "style" && typeof value === "object") {
      for (const [prop, v] of Object.entries(value)) {
        if (prop.startsWith("--")) el.style.setProperty(prop, v); else el.style[prop] = v;
      }
    }
    else if (key === "dataset") Object.assign(el.dataset, value);
    else if (key === "html") el.innerHTML = value; // trusted, build-time HTML only
    else el.setAttribute(key, value === true ? "" : String(value));
  }
  append(el, children);
  return el;
}

export function svg(tag, attrs = {}, ...children) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, String(value));
  }
  append(el, children);
  return el;
}

function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

export function clear(el) { while (el.firstChild) el.firstChild.remove(); return el; }

export function emit(el, name, detail) {
  el.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));
}

export function params() { return new URLSearchParams(location.search); }

export function setParam(key, value, { replace = true } = {}) {
  const url = new URL(location.href);
  if (value == null || value === "") url.searchParams.delete(key);
  else url.searchParams.set(key, value);
  history[replace ? "replaceState" : "pushState"](null, "", url);
}
