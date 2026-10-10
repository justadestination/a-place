import { h } from "../../js/core/dom.js";

/**
 * Slot 3: Syndicated summary slot.
 * Generated from the day's events. Never out-shouts the hero.
 * Eyebrow: NightCal (with NightCal mark)
 * Title: Link to downtown listings / daily rundown.
 */
export function hubSummary(summary = null, { level = 2 } = {}) {
  const container = h("section.nc-hub-slot.nc-hub-summary", { "aria-label": "Daily summary" });
  
  const eyebrow = h("p.nc-eyebrow", {},
    h("img", { src: "/assets/brand/nightcal-accent.png", alt: "", width: "16", height: "16", style: "vertical-align: middle; margin-inline-end: 6px; display: inline-block;" }),
    "NightCal"
  );

  const titleText = summary?.headline || "Downtown Rundown";
  const titleLink = h("a", { href: summary?.url || "/today/", style: "color: inherit; text-decoration: none;" }, titleText);

  container.append(
    h("header.nc-hub-slot__header", {},
      eyebrow,
      h(`h${level}.nc-hub-slot__title`, {}, titleLink),
    ),
    h("p.nc-hub-slot__body", {}, summary?.text || summary?.content || "Downtown Santa Rosa live entertainment overview. Tap to explore tonight's full chronological roster.")
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
