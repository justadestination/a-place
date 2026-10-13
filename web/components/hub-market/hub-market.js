import { h } from "../../js/core/dom.js";

/**
 * Slot 5: SerendipiLyst. The market page is the WorldSum map.
 * Names who is bored nearby. Never out-shouts the hero.
 */
export function hubMarket(market = null, { level = 2 } = {}) {
  const container = h("section.nc-hub-slot.nc-hub-market", { "aria-label": "WorldSum" });

  const eyebrow = h("p.nc-eyebrow", {},
    h("img", { src: "/assets/brand/serendipilyst-accent.png", alt: "", width: "16", height: "16", style: "vertical-align: middle; margin-inline-end: 6px; display: inline-block;" }),
    "SerendipiLyst"
  );

  const titleLink = h("a", { href: "/market/", style: "color: inherit; text-decoration: none;" }, "WorldSum");

  container.append(
    h("header.nc-hub-slot__header", {},
      eyebrow,
      h(`h${level}.nc-hub-slot__title`, {}, titleLink),
    )
  );

  const defaultItems = [
    { title: "Lumen", desc: "Bored at Courthouse Square." },
    { title: "Jules", desc: "Bored at the lot." },
    { title: "Mara", desc: "Bored at Dark Pool." },
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
    h("a.nc-hub-slot__link", { href: "/market/", style: "display: inline-block; margin-block-start: 8px;" }, "Open the map")
  );

  return container;
}

export const meta = {
  name: "hub-market",
  title: "Hub market slot",
  summary: "SerendipiLyst anonymous classifieds slot for the hub index. Independently frameable.",
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
