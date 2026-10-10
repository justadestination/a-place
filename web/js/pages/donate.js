import { h } from "../core/dom.js";
import "../core/theme.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";
import { button } from "../../components/button/button.js";

// Configurable Stripe Payment Link (can be overridden globally via window.STRIPE_DONATION_URL)
const STRIPE_URL = window.STRIPE_DONATION_URL || "https://buy.stripe.com/nightcal";

// Monero address (Zero-tracking anonymous contribution)
const FLEET_XMR_ADDRESS = "888tNkZrPN6JsEgekjMnABU4TBmb2Dt29UWVazRtZ625HRNVozPXDeGXAicP9neuCX2cegwLiohL68qU1N1W9wys1V7quC6";

export function donatePage() {
  const root = h("main.nc-container.nc-page", { id: "main", tabindex: "-1" });

  const hero = h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
    h("p.nc-eyebrow", {}, "Network & Infrastructure"),
    h("h1.nc-h1", {}, "Support the Network"),
    h("p.nc-lede", {}, "NightCal and ShadeNet operate an independent, ad-free privacy nodes, local zine broadsides, and downtown venue scrapers."),
    h("div", {
      style: {
        padding: "var(--nc-space-4)",
        borderRadius: "var(--nc-radius-md)",
        background: "rgba(245, 158, 11, 0.1)",
        border: "1px solid rgba(245, 158, 11, 0.3)",
        marginBlock: "var(--nc-space-2)"
      }
    },
      h("p", {
        style: {
          fontSize: "1.1rem",
          fontWeight: "700",
          color: "var(--nc-color-accent)",
          margin: 0
        }
      }, "Any contributions to network costs are very appreciated.")
    )
  );

  const tiers = [
    {
      title: "Fuel a Node",
      amount: "$5",
      desc: "One-time contribution toward monthly VPS compute, Unbound DNS, and privacy routing for our downtown edge nodes.",
      action: "Contribute $5 with Stripe"
    },
    {
      title: "Network Supporter",
      amount: "$20",
      desc: "One-time contribution helping cover pruned Monero blockchain validation, automated supervisor scrapers, and encrypted backups.",
      action: "Contribute $20 with Stripe"
    },
    {
      title: "Patron of the Shade",
      amount: "$50",
      desc: "One-time contribution funding print broadside runs, autonomous Steward agent development, and independent local venue journalism.",
      action: "Contribute $50 with Stripe"
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
          if (STRIPE_URL.startsWith("http")) {
            window.open(STRIPE_URL, "_blank", "noopener,noreferrer");
          } else {
            alert(`Redirecting to Stripe contribution portal: ${STRIPE_URL}`);
          }
        }
      })
    );
    tierGrid.append(card);
  });

  // Crypto / Monero Privacy Contribution section
  const privacySection = h("section.nc-card-panel", {
    style: {
      padding: "var(--nc-space-5)",
      border: "var(--nc-size-border) solid var(--nc-color-border)",
      borderRadius: "var(--nc-radius-lg)",
      background: "var(--nc-color-surface)",
      marginTop: "var(--nc-space-4)",
      display: "grid",
      gap: "var(--nc-space-3)"
    }
  },
    h("h2.nc-h2", {}, "🔒 Anonymous Contribution (Monero / XMR)"),
    h("p.nc-muted", {}, "Prefer zero financial surveillance? Support the hosting without credit card logs or corporate tracking:"),
    h("div", {
      style: {
        background: "var(--nc-color-bg)",
        padding: "var(--nc-space-3)",
        borderRadius: "var(--nc-radius-md)",
        fontFamily: "monospace",
        fontSize: "0.85rem",
        wordBreak: "break-all",
        border: "1px solid var(--nc-color-border)"
      }
    }, FLEET_XMR_ADDRESS),
    h("p.nc-muted", { style: { fontSize: "0.85rem" } }, "All Monero contributions go directly to hosting and network infrastructure expenses.")
  );

  root.append(hero, tierGrid, privacySection);
  return root;
}

const app = document.getElementById("app");
if (app) {
  app.replaceChildren(siteHeader(), donatePage(), siteFooter());
}
