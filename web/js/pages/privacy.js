import { h } from "../core/dom.js";
import "../core/theme.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";

export function privacyPage() {
  const root = h("main.nc-container.nc-page", { id: "main", tabindex: "-1" });

  const hero = h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
    h("p.nc-eyebrow", {}, "Patron Rights"),
    h("h1.nc-h1", {}, "Privacy Policy"),
    h("p.nc-lede", {}, "We believe nightlife is private. We do not track you, sell your data, or maintain patron surveillance.")
  );

  const content = h("article.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-6)", maxWidth: "var(--nc-size-measure)" } },
    h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("h2.nc-h2", {}, "1. Zero Tracking & No Third-Party Analytics"),
      h("p", {}, "NightCal contains zero tracking cookies, zero marketing pixels, and zero third-party analytics scripts (like Google Analytics, Meta Pixel, or data brokers)."),
      h("p", {}, "When you browse downtown events, your visit is completely anonymous. Our servers record only ephemeral technical request logs required to serve static assets, which are rotated and discarded daily.")
    ),

    h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("h2.nc-h2", {}, "2. What is Stored on Your Device"),
      h("p", {}, "We store minimal data in your device's browser localStorage solely for functionality you choose:"),
      h("ul.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-2)", paddingLeft: "1.25rem" } },
        h("li", {}, h("strong", {}, "Display & Theme Preferences: "), "Your light/dark mode selection, text scaling factor, and motion preferences."),
        h("li", {}, h("strong", {}, "ZKP Token: "), "When you verify age to activate your Personal Steward, a cryptographically signed token is stored locally to maintain your verified session.")
      ),
      h("p", {}, "You can wipe this data at any time by clearing your browser storage or using the 'Reset Verification' button in the Steward drawer.")
    ),

    h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("h2.nc-h2", {}, "3. Zero-Knowledge Proofs (ZKP)"),
      h("p", {}, "Unlike conventional platforms that demand your driver's license or phone number, our 21+ verification uses Zero-Knowledge Proof cryptography."),
      h("p", {}, "The proof mathematical verifies that you are 21 or older without exposing your name, exact birthday, address, or government identification number to our servers or anyone else.")
    ),

    h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("h2.nc-h2", {}, "4. Account Deletion & Data Portability"),
      h("p", {}, "Because we do not store patron accounts in a central database, there is no dossier to delete. You retain 100% control over your personal keys and local steward storage at all times.")
    )
  );

  root.append(hero, content);
  return root;
}

const app = document.getElementById("app");
if (app) {
  app.replaceChildren(siteHeader(), privacyPage(), siteFooter());
}
