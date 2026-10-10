import { h } from "../core/dom.js";
import "../core/theme.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";
import { button } from "../../components/button/button.js";

export function donatePage() {
  const root = h("main.nc-container.nc-page", { id: "main", tabindex: "-1" });

  const hero = h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
    h("p.nc-eyebrow", {}, "Community Backing"),
    h("h1.nc-h1", {}, "Support & Donate"),
    h("p.nc-lede", {}, "Keep NightCal independent, ad-free, and community-driven. Support open source development and local venue journalism.")
  );

  const tiers = [
    {
      title: "Night Patron",
      amount: "$5 / mo",
      desc: "Covers hosting, scraper compute, and keeps NightCal free of advertising and corporate trackers.",
      action: "Become a Patron"
    },
    {
      title: "Zine Supporter",
      amount: "$15 / mo",
      desc: "Funds investigative dispatches, AI model compute (Gemini, Claude, Hermes), and print broadside runs.",
      action: "Support the Zine"
    },
    {
      title: "Venue & Cultural Sponsor",
      amount: "$50 / mo",
      desc: "Helps downtown independent venues operate local nodes, custom merchandise tables, and live event streams.",
      action: "Sponsor a Venue"
    }
  ];

  const tierGrid = h("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 18rem), 1fr))",
      gap: "var(--nc-space-4)",
      marginBlock: "var(--nc-space-4)"
    }
  });

  tiers.forEach(tier => {
    const card = h("article.nc-card-panel", {
      style: {
        padding: "var(--nc-space-5)",
        border: "var(--nc-size-border) solid var(--nc-color-border)",
        borderRadius: "var(--nc-radius-lg)",
        background: "var(--nc-color-surface)",
        display: "grid",
        gap: "var(--nc-space-3)"
      }
    },
      h("h3.nc-h3", {}, tier.title),
      h("p", { style: { fontSize: "var(--nc-font-size-2xl)", fontWeight: "800", color: "var(--nc-color-accent)" } }, tier.amount),
      h("p.nc-muted", { style: { lineHeight: "1.5" } }, tier.desc),
      button({
        label: tier.action,
        variant: "primary",
        onClick: () => {
          alert(`Thank you for supporting NightCal! Redirecting to community contribution portal.`);
        }
      })
    );
    tierGrid.append(card);
  });

  const merchSection = h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-4)", marginTop: "var(--nc-space-6)" } },
    h("h2.nc-h2", {}, "Merch & Venue Shop Integration"),
    h("p", {}, "We are building direct store integrations into venue pages so patrons can purchase merchandise, band vinyl, and tickets directly without high middleman fees:"),
    h("ul.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-2)", paddingLeft: "1.25rem" } },
      h("li", {}, h("strong", {}, "Umwelt Horizons Print Editions: "), "Limited risograph-printed broadsides and archival copies."),
      h("li", {}, h("strong", {}, "Downtown Venue Merch: "), "Direct integration with Shopify and local venue point-of-sale systems for t-shirts, pins, and drink coins."),
      h("li", {}, h("strong", {}, "Artist Direct: "), "100% of band merchandise revenue flows directly to the performing artists.")
    )
  );

  root.append(hero, tierGrid, merchSection);
  return root;
}

const app = document.getElementById("app");
if (app) {
  app.replaceChildren(siteHeader(), donatePage(), siteFooter());
}
