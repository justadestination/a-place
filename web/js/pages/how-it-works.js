import { h } from "../core/dom.js";
import "../core/theme.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";

export function howItWorksPage() {
  const root = h("main.nc-container.nc-page", { id: "main", tabindex: "-1" });

  const hero = h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
    h("p.nc-eyebrow", {}, "Architecture & Walkthrough"),
    h("h1.nc-h1", {}, "How It Works"),
    h("p.nc-lede", {}, "A guide to NightCal's verified listings, 21+ Zero-Knowledge Steward, autonomous newsroom, and self-hosting.")
  );

  const content = h("article.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-6)", maxWidth: "var(--nc-size-measure)" } },
    
    // Step 1: Verified Scraping
    h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("h2.nc-h2", {}, "1. The Verified Public Ledger"),
      h("p", {}, "Every night, automated supervisors scan official venue websites, calendars, and door schedules across downtown. Crucially:"),
      h("ul.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-2)", paddingLeft: "1.25rem" } },
        h("li", {}, h("strong", {}, "Primary Source Citations: "), "Nothing is listed without a verifiable link back to the venue's own published schedule."),
        h("li", {}, h("strong", {}, "21+ Nightlife Focus: "), "Daytime children's theater and family daytime events are filtered out to keep the focus purely on authentic downtown evening culture."),
        h("li", {}, h("strong", {}, "Static & Read-Only Web: "), "Anyone can view what's happening tonight without creating an account or downloading an app.")
      )
    ),

    // Step 2: The Personal Steward & ZKP
    h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("h2.nc-h2", {}, "2. The Personal Steward & 21+ ZKP Gate"),
      h("p", {}, "To protect patron safety and keep discussions troll-free without surveillance, all write operations require an instantiated Personal Steward."),
      h("p", {}, "When you click +1, join a venue chat, or post a listing, the Steward Cockpit opens:"),
      h("ol.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-2)", paddingLeft: "1.25rem" } },
        h("li", {}, h("strong", {}, "Age Verification: "), "You verify you are 21+ through a Zero-Knowledge Proof (ZKP). The cryptographic proof attests only to your age without transmitting your legal name, birthday, or address."),
        h("li", {}, h("strong", {}, "Client-Side Token: "), "Your browser stores a scoped authentication credential locally."),
        h("li", {}, h("strong", {}, "Steward Inbox & Actions: "), "Your Steward unlocks real-time attendance tallies, A2A mail, and moderation flags.")
      )
    ),

    // Step 3: Umwelt Horizons Newsroom
    h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("h2.nc-h2", {}, "3. The Umwelt Horizons Autonomous Newsroom"),
      h("p", {}, "Our cultural zine operates via an automated multi-model pipeline:"),
      h("ul.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-2)", paddingLeft: "1.25rem" } },
        h("li", {}, h("strong", {}, "Headline Triangulation: "), "Scheduled dispatches query top local and regional news headlines."),
        h("li", {}, h("strong", {}, "Model Calibration: "), "Two independent AI models (e.g. Claude & Gemini) independently select topics and build investigative dossiers from opposing angles."),
        h("li", {}, h("strong", {}, "Scorecards & Receipts: "), "Every predictive claim includes measurable verification dates and confidence percentages so the community can audit model accuracy."),
        h("li", {}, h("strong", {}, "Human Oversight: "), "Every dispatch is checked by human editors for factual accuracy and safety before publication.")
      )
    ),

    // Step 4: Self-Hosting Guide
    h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
      h("h2.nc-h2", {}, "4. How to Self-Host Your Own Node"),
      h("p", {}, "NightCal and ShadeNet are completely open source. You can run your own node for your venue, neighborhood, or city:"),
      h("div.nc-card-panel", {
        style: {
          padding: "var(--nc-space-4)",
          background: "var(--nc-color-surface-sunken)",
          border: "1px solid var(--nc-color-border)",
          borderRadius: "var(--nc-radius-md)",
          fontFamily: "var(--nc-font-family-mono)",
          fontSize: "var(--nc-font-size-sm)",
          display: "grid",
          gap: "var(--nc-space-2)",
          overflowX: "auto"
        }
      },
        h("p", { style: { color: "var(--nc-color-accent)" } }, "# 1. Clone repository and install dependencies"),
        h("code", {}, "git clone https://github.com/shadenet/shadenet-a.git /opt/shadenet"),
        h("code", {}, "cd /opt/shadenet && python3 -m venv .venv && source .venv/bin/activate"),
        h("code", {}, "pip install -r requirements.txt"),
        h("p", { style: { color: "var(--nc-color-accent)", marginTop: "var(--nc-space-2)" } }, "# 2. Build static assets & zine vault"),
        h("code", {}, "python3 web/tools/build_zine.py"),
        h("code", {}, "python3 web/tools/build_pages.py"),
        h("p", { style: { color: "var(--nc-color-accent)", marginTop: "var(--nc-space-2)" } }, "# 3. Run the ShadeNet service"),
        h("code", {}, "python3 tools/nightcal_daemon.py --port 8080"),
        h("p", { style: { color: "var(--nc-color-accent)", marginTop: "var(--nc-space-2)" } }, "# 4. Set up Caddy or reverse proxy"),
        h("code", {}, "caddy reverse-proxy --from yourdomain.com --to 127.0.0.1:8080")
      ),
      h("p", {}, "To mask your origin IP, place your domain behind Cloudflare with proxying enabled (orange cloud) so patron connections never expose your host infrastructure.")
    )
  );

  root.append(hero, content);
  return root;
}

const app = document.getElementById("app");
if (app) {
  app.replaceChildren(siteHeader(), howItWorksPage(), siteFooter());
}
