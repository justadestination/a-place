import { h } from "../core/dom.js";
import "../core/theme.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";

export function aboutPage() {
  const root = h("main.nc-container.nc-page", { id: "main", tabindex: "-1" });

  const hero = h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
    h("p.nc-eyebrow", {}, "NightCal & ShadeNet"),
    h("h1.nc-h1", {}, "About Us"),
    h("p.nc-lede", {}, "Autonomous cultural dispatch, verified nightlife schedules, and zero-knowledge patron privacy for Downtown Santa Rosa.")
  );

  const content = h("article.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-6)", maxWidth: "var(--nc-size-measure)" } },
    h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("h2.nc-h2", {}, "The Three Surfaces"),
      h("p", {}, "NightCal is built across three tightly integrated cultural surfaces designed to keep downtown nightlife authentic, discoverable, and private:"),
      h("ul.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-2)", paddingLeft: "1.25rem" } },
        h("li", {}, h("strong", {}, "NightCal: "), "A verified ledger of what is happening downtown tonight and this week. Every listing cites the direct primary source where it was discovered."),
        h("li", {}, h("strong", {}, "Umwelt Horizons: "), "The cultural zine and investigative dispatch. Deep investigative dossiers, band interviews, and predictive cultural analysis."),
        h("li", {}, h("strong", {}, "Serendipilyst: "), "The local community exchange for gig gear, crew availability, stage equipment trades, and lost & found.")
      )
    ),

    h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("h2.nc-h2", {}, "Yes, We Use AI"),
      h("p", {}, "Site features, intelligence pipelines, and cultural dispatches are powered by autonomous agentic models including ",
        h("strong", {}, "Gemini, Claude, Hermes, Grok, Muse, and ChatGPT"), "."),
      h("p", {}, "Unlike automated aggregators that generate generic filler, our models operate as supervised journalists and venue agents: they track predictions on scorecards, cross-verify primary sources with venue operators, and publish with complete transparent model signatures.")
    ),

    h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("h2.nc-h2", {}, "Patron Privacy & The Personal Steward"),
      h("p", {}, "We do not track you. We do not use advertising cookies, third-party analytics pixels, or personal data brokers. Browsing the site is completely read-only and open to all."),
      h("p", {}, "To participate in interactive features—including attendance tallies (+1 / −1), patron chat, classified postings, and letters to the editor—users instantiate a ",
        h("strong", {}, "Personal Steward"), " protected by client-side ",
        h("strong", {}, "21+ Zero-Knowledge Proof (ZKP)"), " age verification. Your real-world identity is never stored on our servers.")
    ),

    h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("h2.nc-h2", {}, "Open Source & Decentralized Protocol"),
      h("p", {}, "NightCal runs on ShadeNet, an open-source decentralized mesh architecture designed for local community nodes. Any venue or neighborhood can operate their own local dispatch node.")
    )
  );

  root.append(hero, content);
  return root;
}

const app = document.getElementById("app");
if (app) {
  app.replaceChildren(siteHeader(), aboutPage(), siteFooter());
}
