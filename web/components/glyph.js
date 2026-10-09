// Shape glyphs. Kinds and node types are told apart by shape AND text label,
// never by colour alone (WCAG 1.4.1). Colour comes from currentColor, which the
// caller sets from a token.
import { svg } from "../js/core/dom.js";

const SHAPES = {
  circle: () => svg("circle", { cx: 6, cy: 6, r: 5 }),
  diamond: () => svg("polygon", { points: "6,0.6 11.4,6 6,11.4 0.6,6" }),
  square: () => svg("rect", { x: 1.25, y: 1.25, width: 9.5, height: 9.5, rx: 1.5 }),
  triangle: () => svg("polygon", { points: "6,0.8 11.6,11 0.4,11" }),
  hexagon: () => svg("polygon", { points: "3.1,0.9 8.9,0.9 11.8,6 8.9,11.1 3.1,11.1 0.2,6" }),
  ring: () => svg("circle", { cx: 6, cy: 6, r: 4.2, fill: "none", stroke: "currentColor", "stroke-width": 2.2 }),
};

export const GLYPHS = Object.keys(SHAPES);

export function glyph(shape = "circle", { className = "nc-glyph" } = {}) {
  const make = SHAPES[shape] || SHAPES.circle;
  return svg("svg", { class: className, viewBox: "0 0 12 12", "aria-hidden": "true", focusable: "false", fill: "currentColor" }, make());
}

/** SVG path data for a glyph centred on 0,0 with radius r (used by the node map). */
export function glyphPath(shape, r) {
  const k = r / 6;
  const pts = {
    diamond: [[0, -6], [6, 0], [0, 6], [-6, 0]],
    square: [[-5, -5], [5, -5], [5, 5], [-5, 5]],
    triangle: [[0, -5.6], [6, 5], [-6, 5]],
    hexagon: [[-3, -5.2], [3, -5.2], [6, 0], [3, 5.2], [-3, 5.2], [-6, 0]],
  }[shape];
  if (!pts) return `M ${-r} 0 a ${r} ${r} 0 1 0 ${2 * r} 0 a ${r} ${r} 0 1 0 ${-2 * r} 0 Z`;
  return pts.map(([x, y], i) => `${i ? "L" : "M"} ${(x * k).toFixed(2)} ${(y * k).toFixed(2)}`).join(" ") + " Z";
}
