import { h } from "../core/dom.js";
import "../core/theme.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";
import { button } from "../../components/button/button.js";

export function zombieCrawlPage() {
  const root = h("main.nc-container.nc-page", { id: "main", tabindex: "-1" });

  // Hero Section with Zombie Accents
  const hero = h("section.nc-card-panel", {
    style: {
      padding: "var(--nc-space-6)",
      borderRadius: "var(--nc-radius-xl, 16px)",
      background: "radial-gradient(circle at top right, rgba(132, 204, 22, 0.15), rgba(15, 23, 42, 0.95))",
      border: "2px solid #84cc16",
      boxShadow: "0 0 30px rgba(132, 204, 22, 0.25), inset 0 0 20px rgba(132, 204, 22, 0.08)",
      display: "grid",
      gap: "var(--nc-space-3)",
      position: "relative",
      overflow: "hidden"
    }
  },
    h("div", {
      style: {
        display: "inline-flex",
        alignItems: "center",
        gap: "0.5rem",
        background: "rgba(132, 204, 22, 0.2)",
        border: "1px solid #84cc16",
        padding: "0.3rem 0.85rem",
        borderRadius: "9999px",
        width: "fit-content",
        fontSize: "0.85rem",
        fontWeight: "800",
        color: "#84cc16",
        letterSpacing: "0.05em"
      }
    }, "🧟 OFFICIAL EVENT GUIDE · TONIGHT · 6:00 PM – 2:00 AM"),
    h("h1.nc-h1", {
      style: {
        fontSize: "clamp(2rem, 5vw, 3.2rem)",
        fontWeight: "900",
        letterSpacing: "-0.03em",
        color: "#f4f4f5",
        textShadow: "0 0 15px rgba(132, 204, 22, 0.4)"
      }
    }, "Downtown Santa Rosa Zombie Crawl 2026"),
    h("p.nc-lede", {
      style: {
        fontSize: "1.15rem",
        lineHeight: "1.6",
        color: "#d4d4d8"
      }
    }, "The living dead return to Fourth Street and Railroad Square! Put on your best decaying attire, fake blood, and shredded threads for a multi-venue bar walk through downtown's finest rooms."),
    h("div", { style: "display: flex; gap: 0.75rem; flex-wrap: wrap; margin-top: 0.5rem;" },
      button({
        label: "📷 Open 21+ Bar Door Scanner",
        variant: "primary",
        onClick: () => { window.location.href = "/door-scanner/"; }
      }),
      button({
        label: "📅 View on NightCal Calendar",
        variant: "ghost",
        onClick: () => { window.location.href = "/?date=2026-10-10"; }
      })
    )
  );

  // Stop-by-Stop Itinerary
  const stops = [
    {
      step: "Stop 1 · 6:00 PM – 7:30 PM",
      venue: "Shady Oak Barrel House",
      address: "420 1st Street",
      highlights: "Kickoff HQ & Makeup Station. Fresh sour ale drafts, outdoor patio gathering, and fake blood touchups.",
      special: "🧪 The Reanimator Sour Ale"
    },
    {
      step: "Stop 2 · 7:30 PM – 9:00 PM",
      venue: "Barrel Proof Lounge",
      address: "501 Mendocino Avenue",
      highlights: "Live horror rock DJ, cocktail lounge vibes, and preliminary costume contest heats.",
      special: "🍸 Brain Haemorrhage Shots & Smoked Bourbon"
    },
    {
      step: "Stop 3 · 9:00 PM – 10:15 PM",
      venue: "Beer Baron Bar & Kitchen",
      address: "614 4th Street",
      highlights: "Fourth Street midway takeover. Huge craft tap wall, whiskey flights, and zombie photos.",
      special: "🥃 Witches Brew Whiskey Flight"
    },
    {
      step: "Stop 4 · 10:15 PM – 11:30 PM",
      venue: "Stout Brothers Irish Pub",
      address: "523 4th Street",
      highlights: "Classic dark wood pub chaos, full undead chorus singing, and costume showdown.",
      special: "🍺 Black & Tan 'Nightfall' Pints"
    },
    {
      step: "Stop 5 · 11:30 PM – 1:00 AM",
      venue: "The California Theatre",
      address: "528 7th Street",
      highlights: "Midnight Monster Mash! Horror movie projections on the big stage and live dance floor.",
      special: "🩸 Vampire's Kiss Cocktail"
    },
    {
      step: "Stop 6 · 1:00 AM – 2:00 AM",
      venue: "The Goose & Fern",
      address: "Historic Railroad Square",
      highlights: "The Graveyard Shift. Late night nightcaps and survivor photo for those who made the full trek.",
      special: "🦇 Final Survivor Boilermaker"
    }
  ];

  const routeSection = h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-4)", marginTop: "var(--nc-space-6)" } },
    h("div", {},
      h("h2.nc-h2", {}, "🗺️ Official Crawl Route & Schedule"),
      h("p.nc-muted", {}, "Follow the horde from First Street through Fourth Street to Railroad Square. Jump in at any stop:")
    ),
    h("div.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-4)" } },
      ...stops.map((stop, i) =>
        h("article.nc-card-panel", {
          style: {
            padding: "var(--nc-space-5)",
            borderRadius: "var(--nc-radius-lg)",
            border: "1px solid var(--nc-color-border)",
            background: "var(--nc-color-surface)",
            display: "grid",
            gap: "var(--nc-space-2)",
            position: "relative"
          }
        },
          h("div", { style: "display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 0.5rem;" },
            h("span", {
              style: "font-size: 0.85rem; font-weight: 700; color: #84cc16; text-transform: uppercase;"
            }, stop.step),
            h("span.nc-muted", { style: "font-size: 0.85rem;" }, stop.address)
          ),
          h("h3.nc-h3", { style: "font-size: 1.3rem; font-weight: 800;" }, stop.venue),
          h("p.nc-muted", { style: "line-height: 1.5;" }, stop.highlights),
          h("div", {
            style: {
              background: "rgba(239, 68, 68, 0.1)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              padding: "0.4rem 0.75rem",
              borderRadius: "6px",
              fontSize: "0.88rem",
              fontWeight: "600",
              color: "#f87171",
              width: "fit-content",
              marginTop: "0.25rem"
            }
          }, `Drink Special: ${stop.special}`)
        )
      )
    )
  );

  // 21+ Fast Door Admission Callout
  const doorCallout = h("section.nc-card-panel", {
    style: {
      padding: "var(--nc-space-6)",
      borderRadius: "var(--nc-radius-xl)",
      background: "rgba(16, 185, 129, 0.08)",
      border: "2px solid var(--nc-color-success, #10b981)",
      marginTop: "var(--nc-space-6)",
      display: "grid",
      gap: "var(--nc-space-3)"
    }
  },
    h("h2.nc-h2", { style: "color: var(--nc-color-success, #10b981);" }, "⚡ 21+ Fast Door Verification"),
    h("p", { style: "line-height: 1.6;" },
      "Skip the paper ID bottlenecks at the door! Participating downtown venues accept digital driver's licenses via the ",
      h("strong", {}, "California DMV Wallet"),
      ", Apple Wallet, and ShadeNet Zero-Knowledge passes. Door staff will scan your phone camera QR code for instant 500ms admission with ",
      h("strong", {}, "Zero PII stored"),
      "."
    ),
    h("div", { style: "display: flex; gap: 0.75rem; flex-wrap: wrap;" },
      button({
        label: "Open Bar Door Camera Scanner",
        variant: "primary",
        onClick: () => { window.location.href = "/door-scanner/"; }
      }),
      button({
        label: "Read Bouncer & Operator Guide",
        variant: "ghost",
        onClick: () => { window.location.href = "/changelog/"; }
      })
    )
  );

  // Crawlers Survival Guidelines
  const rules = [
    { rule: "1. No Real Weapons", desc: "Prop scythes, chainsaws, or bats must be foam, cardboard, or plastic. Zero exceptions." },
    { rule: "2. Respect Downtown", desc: "Stick to sidewalks, don't harass non-crawlers or frighten young kids outside venues." },
    { rule: "3. 21+ Entry Required", desc: "Bring physical government ID or your verified CA DMV Mobile Driver's License." },
    { rule: "4. Hydrate & Stay Safe", desc: "Drink water between stops. Use rideshares, taxis, or designate an un-infected sober driver." },
    { rule: "5. Tip the Staff", desc: "Zombies tip heavily. Take care of downtown's bartenders and door staff!" }
  ];

  const guidelinesSection = h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-4)", marginTop: "var(--nc-space-6)" } },
    h("h2.nc-h2", {}, "🧠 Undead Survival Rules"),
    h("div", {
      style: {
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 16rem), 1fr))",
        gap: "var(--nc-space-3)"
      }
    },
      ...rules.map(r =>
        h("div.nc-card-panel", {
          style: {
            padding: "var(--nc-space-4)",
            borderRadius: "var(--nc-radius-md)",
            border: "1px solid var(--nc-color-border)",
            background: "var(--nc-color-surface)"
          }
        },
          h("h4", { style: "font-weight: 700; margin-bottom: 0.35rem;" }, r.rule),
          h("p.nc-muted", { style: "font-size: 0.85rem; line-height: 1.45;" }, r.desc)
        )
      )
    )
  );

  root.append(hero, routeSection, doorCallout, guidelinesSection);
  return root;
}

const app = document.getElementById("app");
if (app) {
  app.replaceChildren(siteHeader(), zombieCrawlPage(), siteFooter());
}
