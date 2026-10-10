import { h } from "../core/dom.js";
import "../core/theme.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";

export function termsPage() {
  const root = h("main.nc-container.nc-page", { id: "main", tabindex: "-1" });

  const hero = h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
    h("p.nc-eyebrow", {}, "Legal & Guidelines"),
    h("h1.nc-h1", {}, "Terms & Conditions"),
    h("p.nc-lede", {}, "Community rules, age requirements, and terms of service for NightCal, Umwelt Horizons, and Serendipilyst.")
  );

  const content = h("article.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-6)", maxWidth: "var(--nc-size-measure)" } },
    h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("h2.nc-h2", {}, "1. 21+ Requirement for Interactive Participation"),
      h("p", {}, "While NightCal's event calendar is publicly viewable by anyone, all interactive features—including attendance tallying (+1 / −1), patron chat, classified listings, and zine commentary—are strictly restricted to patrons aged 21 and older."),
      h("p", {}, "Verification is enforced cryptographically using zero-knowledge proofs. Any attempt to forge credentials or circumvent age gating will result in immediate steward revocation.")
    ),

    h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("h2.nc-h2", {}, "2. Accuracy of Listings & Primary Sources"),
      h("p", {}, "NightCal indexes events directly from official venue websites and verified local organizers. However, schedules, set times, door covers, and performer line-ups are subject to change without notice."),
      h("p", {}, "Always verify with the host venue before making travel or ticket arrangements. NightCal is an independent cultural ledger and is not liable for cancellations, delays, or venue policy changes.")
    ),

    h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("h2.nc-h2", {}, "3. Autonomous AI Reporting & Opinion"),
      h("p", {}, "Articles, reviews, and forecasts in Umwelt Horizons are produced using artificial intelligence models (Gemini, Claude, Hermes, Grok, ChatGPT) under human supervision."),
      h("p", {}, "Predictive claims and analysis are cultural commentary and forecasts, not financial, legal, or medical advice.")
    ),

    h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("h2.nc-h2", {}, "4. Community Conduct & Moderation"),
      h("p", {}, "Harassment, hate speech, spam, ticket scalping, and malicious behavior are strictly prohibited. The ShadeNet operator console reviews community flags, and violating stewards are removed from the network.")
    )
  );

  root.append(hero, content);
  return root;
}

const app = document.getElementById("app");
if (app) {
  app.replaceChildren(siteHeader(), termsPage(), siteFooter());
}
