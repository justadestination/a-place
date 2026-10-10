import { h } from "../../js/core/dom.js";

/**
 * Slot 2: Zine article slot (Umwelt Horizons).
 * Never out-shouts the hero today timeline.
 */
export function hubZine(article = null, { level = 2 } = {}) {
  const container = h("section.nc-hub-slot.nc-hub-zine", { "aria-label": "Zine feature" });
  
  if (!article) {
    container.append(
      h("header.nc-hub-slot__header", {},
        h("p.nc-eyebrow", {}, h("img", { src: "/assets/brand/uh-accent.png", alt: "", width: "20", height: "13", style: "vertical-align: middle; margin-inline-end: 6px; display: inline-block;" }), "Umwelt (Zine)"),
        h(`h${level}.nc-hub-slot__title`, {}, "Latest Dispatch"),
      ),
      h("p.nc-hub-slot__empty", {}, "No zine dispatch scheduled today.")
    );
    return container;
  }

  container.append(
    h("header.nc-hub-slot__header", {},
      h("p.nc-eyebrow", {}, "Umwelt Horizons"),
      h(`h${level}.nc-hub-slot__title`, {}, article.title || "Untitled"),
    ),
    h("p.nc-hub-slot__body", {}, article.excerpt || article.summary || ""),
    article.url ? h("a.nc-hub-slot__link", { href: article.url }, "Read article →") : null
  );
  return container;
}

export const meta = {
  name: "hub-zine",
  title: "Hub zine slot",
  summary: "Zine article slot for the hub index: featured Umwelt Horizons piece. Independently frameable.",
  params: { title: "override title", excerpt: "override excerpt" },
};

export async function embed(params) {
  const title = params.get("title");
  const excerpt = params.get("excerpt");
  if (!title && !excerpt) {
    return hubZine(null);
  }
  return hubZine({ title: title || "Sample Dispatch", excerpt: excerpt || "A peek through the camera into the downtown evening.", url: "/zine/" });
}
