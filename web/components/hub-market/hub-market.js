import { h } from "../../js/core/dom.js";

/**
 * Slot 5: Market slot (Serendipilyst anonymous classifieds).
 * Aggregated from Flags. Never out-shouts the hero.
 */
export function hubMarket(market = null, { level = 2 } = {}) {
  const container = h("section.nc-hub-slot.nc-hub-market", { "aria-label": "Market postings" });
  
  if (!market || !market.items || market.items.length === 0) {
    container.append(
      h("header.nc-hub-slot__header", {},
        h("p.nc-eyebrow", {}, "Serendipilyst"),
        h(`h${level}.nc-hub-slot__title`, {}, "Community Market"),
      ),
      h("p.nc-hub-slot__empty", {}, "No active market exposures. Post an anonymous flag downtown.")
    );
    return container;
  }

  const items = market.items.map(it => h("li.nc-hub-market__item", {},
    h("span.nc-hub-market__title", {}, it.title || "Listing"),
    h("span.nc-hub-market__desc", {}, it.desc || "")
  ));

  container.append(
    h("header.nc-hub-slot__header", {},
      h("p.nc-eyebrow", {}, "Serendipilyst"),
      h(`h${level}.nc-hub-slot__title`, {}, `Community Market (${market.items.length})`),
    ),
    h("ul.nc-hub-market__list", {}, items)
  );
  return container;
}

export const meta = {
  name: "hub-market",
  title: "Hub market slot",
  summary: "Serendipilyst anonymous classifieds slot for the hub index. Independently frameable.",
  params: { count: "number of items to mock (default 0)" },
};

export async function embed(params) {
  const count = parseInt(params.get("count") || "0", 10);
  if (count <= 0) {
    return hubMarket(null);
  }
  const items = Array.from({ length: count }, (_, i) => ({
    title: `Trade / Service #${i + 1}`,
    desc: "Downtown trade or vintage sound gear.",
  }));
  return hubMarket({ items });
}
