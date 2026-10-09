import { h } from "../../js/core/dom.js";
import { SITE } from "../../js/core/site.js";

/**
 * Footer: the data notes the old page printed above the calendar (status,
 * closures, attribution) live here, behind one "About this data" disclosure.
 * OpenStreetMap attribution stays visible because the licence requires it.
 */
export function siteFooter({ notes = {}, source = "live" } = {}) {
  const about = h("details.nc-site-footer__about", {},
    h("summary", {}, "About this data"),
    h("div.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("p", {}, "Listings come from the downtown events calendar and are checked against each venue's own pages. Nothing is added from a page that does not list the show."),
      notes.closed ? h("p", {}, notes.closed) : null,
      notes.status ? h("p", {}, h("strong", {}, "Last check: "), notes.status) : null,
      source === "sample" ? h("p", {}, "The live listings service did not answer, so this page is showing a saved copy.") : null,
    ),
  );
  return h("footer.nc-site-footer", {},
    h("div.nc-container.nc-site-footer__inner", {},
      about,
      h("p.nc-site-footer__attribution", {}, notes.attribution || "Rooms from OpenStreetMap contributors."),
      h("nav", { "aria-label": "More" }, h("ul.nc-site-footer__links", { role: "list" },
        h("li", {}, h("a", { href: "/system/#embeds" }, "Embed on your site")),
        h("li", {}, h("a", { href: "/3d/" }, "AR preview")),
        h("li", {}, h("a", { href: "/system/" }, "Design system")),
      )),
      h("p.nc-site-footer__name", {}, `${SITE.name} · ${SITE.place}`),
    ),
  );
}

export const meta = {
  name: "site-footer",
  title: "Site footer",
  summary: "About this data (status, closures), the required OpenStreetMap attribution, and secondary links.",
  params: {},
};

export async function embed(params, ctx) {
  const model = await ctx.calendar();
  return siteFooter({ notes: model.notes, source: model.source });
}
