import { h } from "../../js/core/dom.js";
import { glyph } from "../glyph.js";
import { KINDS, kindOf } from "../../js/data/calendar.js";

/** Kind label with its shape glyph. Text is always present; colour is a second cue. */
export function kindTag(kind, { compact = false } = {}) {
  const k = kindOf(kind);
  return h(`span.nc-kind-tag`, { "data-tone": k.tone, class: compact ? "nc-kind-tag--compact" : null }, glyph(k.glyph), h("span", {}, k.label));
}

/** Glyph only, for dense places; the caller must provide the label in text nearby. */
export function kindGlyph(kind) {
  const k = kindOf(kind);
  const g = glyph(k.glyph, { className: "nc-glyph nc-kind-glyph" });
  g.dataset.tone = k.tone;
  return g;
}

export const meta = {
  name: "kind-tag",
  title: "Kind tag",
  summary: "What sort of night it is, as text plus a shape. Six kinds: live music, comedy, show, trivia, food trucks, other.",
  params: { kind: Object.keys(KINDS).join(" | ") + " (omit for all)" },
};

export function embed(params) {
  const kind = params.get("kind");
  return h("div.nc-cluster", {}, (kind ? [kind] : Object.keys(KINDS)).map(k => kindTag(k)));
}
