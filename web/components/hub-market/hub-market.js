import { h } from "../../js/core/dom.js";

/**
 * Slot 5: Market slot (Serendipilyst anonymous classifieds).
 * Renamed to: "Community Listings"
 * Aggregated from Flags. Never out-shouts the hero.
 */
export function hubMarket(market = null, { level = 2 } = {}) {
  const container = h("section.nc-hub-slot.nc-hub-market", { "aria-label": "Market postings" });
  
  const eyebrow = h("p.nc-eyebrow", {},
    h("img", { src: "/assets/brand/serendipilyst-accent.png", alt: "", width: "16", height: "16", style: "vertical-align: middle; margin-inline-end: 6px; display: inline-block;" }),
    "Serendipilyst"
  );

  const count = market?.items?.length || 3;
  const titleLink = h("a", { href: "/market/", style: "color: inherit; text-decoration: none;" }, `Community Listings (${count})`);

  container.append(
    h("header.nc-hub-slot__header", {},
      eyebrow,
      h(`h${level}.nc-hub-slot__title`, {}, titleLink),
    )
  );

  const defaultItems = [
    { title: "Vintage Sansui Tube Amp", desc: "Working condition. In-person cash trade downtown." },
    { title: "Carpool to San Francisco SFJAZZ", desc: "Leaving 4th St Friday 5:30pm, 2 spots open." },
    { title: "Analog Synth Jam & Patch Exchange", desc: "Sunday afternoon patio meetup at Arlene Francis." },
  ];

  const itemsToRender = (market?.items && market.items.length > 0) ? market.items : defaultItems;

  const items = itemsToRender.slice(0, 3).map(it => h("li.nc-hub-market__item", {},
    h("a", { href: "/market/", style: "color: inherit; text-decoration: none;" },
      h("strong.nc-hub-market__title", {}, it.title || "Listing"),
      h("span.nc-hub-market__desc", {}, ` · ${it.desc || ""}`)
    )
  ));

  container.append(
    h("ul.nc-hub-market__list", { style: "list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; font-size: var(--nc-font-size-sm);" }, items),
    h("a.nc-hub-slot__link", { href: "/market/", style: "display: inline-block; margin-block-start: 8px;" }, "Browse all listings →")
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
