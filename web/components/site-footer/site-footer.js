import { h } from "../../js/core/dom.js";
import { SITE } from "../../js/core/site.js";

/**
 * Footer:
 *   - ShadeNet logo watermark centered above footer
 *   - "About this data" disclosure
 *   - OpenStreetMap attribution
 *   - Primary links: About Us · How It Works · T&C · Privacy · iCal Feed · Donate
 *   - AI statement: "Yes, we use AI. Site features work by Gemini, Claude, Hermes, Grok, Muse, and ChatGPT."
 */
export function siteFooter({ notes = {}, source = "live" } = {}) {
  const watermark = h("div.nc-site-footer__watermark", { "aria-hidden": "true" },
    h("img", { src: "/assets/brand/shadenet-accent.png", alt: "", width: "96", height: "96" })
  );

  const about = h("details.nc-site-footer__about", {},
    h("summary", {}, "About this data"),
    h("div.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("p", {}, "Listings come from the downtown events calendar and are checked against each venue's own pages. Nothing is added from a page that does not list the show."),
      notes.status ? h("p", {}, h("strong", {}, "Last check: "), notes.status) : null,
      source === "sample" ? h("p", {}, "The live listings service did not answer, so this page is showing a saved copy.") : null,
    ),
  );

  return h("footer.nc-site-footer", {},
    watermark,
    h("div.nc-container.nc-site-footer__inner", {},
      about,
      h("p.nc-site-footer__attribution", {}, notes.attribution || "Rooms from OpenStreetMap contributors."),
      h("nav", { "aria-label": "Information and Policy" },
        h("ul.nc-site-footer__links", { role: "list" },
          h("li", {}, h("a", { href: "/about/" }, "About Us")),
          h("li", {}, h("a", { href: "/how-it-works/" }, "How It Works")),
          h("li", {}, h("a", { href: "/terms/" }, "Terms & Conditions")),
          h("li", {}, h("a", { href: "/privacy/" }, "Privacy")),
          h("li", {}, h("a", { href: "/calendar/feed.ics" }, "iCal Feed")),
          h("li", {}, h("a", { href: "/donate/" }, "Support & Donate")),
        )
      ),
      h("div.nc-site-footer__meta", {},
        h("p.nc-site-footer__ai-notice", {}, "Yes, we use AI. Site features work by Gemini, Claude, Hermes, Grok, Muse, and ChatGPT."),
        h("p.nc-site-footer__name", {}, `${SITE.name} · ${SITE.place}`)
      )
    ),
  );
}

export const meta = {
  name: "site-footer",
  title: "Site footer",
  summary: "ShadeNet watermark, data disclosure, About/How/Terms/Privacy links, and AI attribution statement.",
  params: {},
};

export async function embed(params, ctx) {
  const model = await ctx.calendar();
  return siteFooter({ notes: model.notes, source: model.source });
}
