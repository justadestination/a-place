import { h } from "../../js/core/dom.js";

/**
 * Slot 3: Syndicated summary slot.
 * Generated from the day's events. Never out-shouts the hero.
 */
export function hubSummary(summary = null, { level = 2 } = {}) {
  const container = h("section.nc-hub-slot.nc-hub-summary", { "aria-label": "Daily summary" });
  
  if (!summary) {
    container.append(
      h("header.nc-hub-slot__header", {},
        h("p.nc-eyebrow", {}, "Nightly Brief"),
        h(`h${level}.nc-hub-slot__title`, {}, "Downtown Rundown"),
      ),
      h("p.nc-hub-slot__empty", {}, "No syndicated summary generated for tonight.")
    );
    return container;
  }

  container.append(
    h("header.nc-hub-slot__header", {},
      h("p.nc-eyebrow", {}, "Nightly Brief"),
      h(`h${level}.nc-hub-slot__title`, {}, summary.headline || "Downtown Tonight"),
    ),
    h("p.nc-hub-slot__body", {}, summary.text || summary.content || "")
  );
  return container;
}

export const meta = {
  name: "hub-summary",
  title: "Hub summary slot",
  summary: "Syndicated daily summary slot for the hub index. Independently frameable.",
  params: { text: "override summary text" },
};

export async function embed(params) {
  const text = params.get("text");
  if (!text) {
    return hubSummary(null);
  }
  return hubSummary({ headline: "Tonight's Pulse", text });
}
