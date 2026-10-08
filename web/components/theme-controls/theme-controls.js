import { h } from "../../js/core/dom.js";
import Theme from "../../js/core/theme.js";
import { button } from "../button/button.js";

let uid = 0;

const GROUPS = [
  { key: "scheme", legend: "Theme", options: [["system", "Match device"], ["light", "Light"], ["dark", "Dark"]], fallback: "system" },
  { key: "textScale", legend: "Text size", options: [[1, "Default"], [1.25, "Large"], [1.5, "Larger"], [2, "Largest"]], fallback: 1 },
  { key: "density", legend: "Spacing", options: [["compact", "Tight"], ["comfortable", "Normal"], ["spacious", "Roomy"]], fallback: "comfortable" },
  { key: "motion", legend: "Motion", options: [["system", "Match device"], ["reduce", "Reduce"], ["full", "Allow"]], fallback: "system" },
];

/**
 * Reader-facing display settings. Every change goes through the public theme
 * API (js/core/theme.js), applies live, and persists. A Steward agent uses
 * the same API, so both stay in sync.
 */
export function themeControls({ title = "Display" } = {}) {
  const id = ++uid;
  const form = h("form.nc-theme-controls", { "aria-label": `${title} settings`, onsubmit: e => e.preventDefault() });
  const sync = spec => {
    for (const g of GROUPS) {
      const value = spec[g.key] ?? g.fallback;
      form.querySelectorAll(`input[name="${g.key}-${id}"]`).forEach(input => { input.checked = String(input.value) === String(value); });
    }
  };
  for (const g of GROUPS) {
    form.append(h("fieldset.nc-theme-controls__group", {},
      h("legend.nc-label", {}, g.legend),
      h("div.nc-segmented__options", {}, g.options.map(([value, text]) =>
        h("label.nc-segmented__option", {},
          h("input", { type: "radio", name: `${g.key}-${id}`, value: String(value), "data-key": g.key }),
          h("span", {}, text)))),
    ));
  }
  const reset = button({ label: "Reset", variant: "ghost", onClick: () => Theme.reset() });
  form.append(h("div.nc-theme-controls__footer", {}, reset));
  form.addEventListener("change", e => {
    const input = e.target;
    if (!input.dataset.key) return;
    const value = input.dataset.key === "textScale" ? Number(input.value) : input.value;
    Theme.apply({ [input.dataset.key]: value });
  });
  sync(Theme.get());
  Theme.subscribe(r => sync(r.spec));
  return form;
}

export const meta = {
  name: "theme-controls",
  title: "Display settings",
  summary: "Theme, text size, spacing and motion, applied live through the public theme API.",
  params: {},
};

export function embed() { return themeControls(); }
