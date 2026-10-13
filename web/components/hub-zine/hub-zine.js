import { h } from "../../js/core/dom.js";

/**
 * Slot 2: Zine article slot (Umwelt Horizons).
 * Never out-shouts the hero today timeline.
 * Eyebrow: Umwelt Horizons (with UH mark)
 * Title: Clickable link to latest dispatch.
 */
export function hubZine(article = null, { level = 2 } = {}) {
  const container = h("section.nc-hub-slot.nc-hub-zine", { "aria-label": "Zine feature" });
  
  const eyebrow = h("p.nc-eyebrow", {},
    h("img", { src: "/assets/brand/uh-crimson-256.png", alt: "", width: "20", height: "13", style: "vertical-align: middle; margin-inline-end: 6px; display: inline-block;" }),
    "Umwelt Horizons"
  );

  const titleText = article?.title || "A Machine with No Thoughts Would Like a Word";
  const targetUrl = article?.url || "/zine/?node=note:a-machine-with-no-thoughts";
  const titleLink = h("a", { href: targetUrl, style: "color: inherit; text-decoration: none;" }, titleText);

  const excerpt = article?.excerpt || article?.summary || "I'm the loom. I made the lace your great-grandmother was married in... An automation cannot be surprised. Not won't: can't.";

  container.append(
    h("header.nc-hub-slot__header", {},
      eyebrow,
      h(`h${level}.nc-hub-slot__title`, {}, titleLink),
    ),
    h("p.nc-hub-slot__body", {}, excerpt),
    h("a.nc-hub-slot__link", { href: targetUrl }, "Read article →")
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
