import { h } from "../../js/core/dom.js";
import { button } from "../button/button.js";

/**
 * Editorial Print Marker Component (Task 3.8)
 */
export function markerCard({
  target = "note:the-room-after-midnight",
  file = "/data/markers/the-room-after-midnight.svg",
  caption = "shady.example.org/portal/?target=note:the-room-after-midnight",
  destinationUrl = "/portal/?target=note:the-room-after-midnight",
  level = 2,
} = {}) {
  const root = h("article.nc-marker-card", { "aria-label": `Visual print marker for ${target}` });

  const header = h("header.nc-marker-card__header", {},
    h("span.nc-marker-card__badge", {}, "Print Marker · 15mm Minimum"),
    h(`h${level}.nc-marker-card__title`, {}, `Marker for ${target}`)
  );

  const imgHolder = h("div.nc-marker-card__preview", {},
    h("img.nc-marker-card__img", {
      src: file,
      alt: `Print marker linking to ${target}`,
      width: "200",
      height: "225",
      loading: "lazy",
    })
  );

  const fallbackCaption = h("p.nc-marker-card__fallback", {},
    h("strong", {}, "Printed Fallback URL: "),
    h("code.nc-marker-card__code", {}, caption)
  );

  const actions = h("div.nc-marker-card__actions", {},
    button({
      label: "Open Portal Destination",
      variant: "secondary",
      href: destinationUrl,
    })
  );

  root.append(header, imgHolder, fallbackCaption, actions);
  return root;
}

export const meta = {
  name: "marker",
  title: "Zine print marker",
  summary: "Visual marker system embedding QR data with high-contrast editorial styling and printed URL fallbacks.",
  params: {
    target: "target node or entity ID (default note:the-room-after-midnight)"
  },
};

export async function embed(params) {
  const target = params.get("target") || "note:the-room-after-midnight";
  const slug = target.replace(/^[^:]+:/, "").toLowerCase().replace(/[^a-z0-9]+/g, "-");
  const file = `/data/markers/${slug}.svg`;
  const caption = `shady.example.org/portal/?target=${target}`;
  const destinationUrl = `/portal/?target=${encodeURIComponent(target)}`;

  return markerCard({ target, file, caption, destinationUrl });
}
