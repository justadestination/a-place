import { h } from "../core/dom.js";
import "../core/theme.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";

export function changelogPage() {
  const root = h("main.nc-container.nc-page", { id: "main", tabindex: "-1" });

  // Hero Section
  const hero = h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
    h("div", {
      style: {
        display: "inline-flex",
        alignItems: "center",
        gap: "0.5rem",
        background: "rgba(16, 185, 129, 0.15)",
        border: "1px solid var(--nc-color-success, #10b981)",
        padding: "0.25rem 0.75rem",
        borderRadius: "9999px",
        width: "fit-content",
        fontSize: "0.85rem",
        fontWeight: "700",
        color: "var(--nc-color-success, #10b981)"
      }
    }, "🟢 ALPHA v1.0.0 (v0.1.0-alpha.1)"),
    h("h1.nc-h1", {}, "Capabilities, Roadmap & Changelog"),
    h("p.nc-lede", {}, "A transparent accounting of everything ShadeNet and NightCal can do today, everything we are building towards, and an immutable log of our releases.")
  );

  // Section 1: What Alpha v1 Can Do Right Now
  const currentCapabilities = [
    {
      title: "1. Cited Downtown Nightlife Intelligence (The Oak & NightCal)",
      items: [
        "Factual database of 50 downtown Santa Rosa venues, verified stages, and active performers.",
        "Strict anti-hallucination guarantee: every single show listing requires an immutable citation URL.",
        "4-Axis interactive Night Sheet calendar: start time (X), venue lanes (Y), community votes (Z-depth), set duration (wire).",
        "Public iCal calendar feed subscription (/calendar/feed.ics) syncing with Apple, Google, and Outlook calendars."
      ]
    },
    {
      title: "2. Zero-Knowledge Age Verification ('Verify ID Without ID')",
      items: [
        "3-way unified cryptographic engine: ISO/IEC 18013-5 California DMV Mobile Driver's License (mDL), ZK-Passport ICAO-9303 Groth16 proofs, and ShadeNet Ed25519 delegations.",
        "Privacy by design: mathematically proves age >= 21 with zero personal data leakage (no names, dates of birth, home addresses, or license numbers stored).",
        "Statutory safe harbor compliance with California Business & Professions Code § 25660."
      ]
    },
    {
      title: "3. Bar Door Camera Scanner Edge Node (PWA)",
      items: [
        "Live standalone camera scanner (/door-scanner/) running in any modern mobile browser.",
        "Sub-second camera scanning of patron Apple Wallet, Google Wallet, and CA DMV Wallet 21+ QR codes.",
        "Tactile feedback: Web Audio double-beep chime and green screen on 21+ ADMITTED, low sawtooth buzz and red screen on ENTRY DENIED.",
        "Live admission counter tracking real-time venue occupancy and entry tallies."
      ]
    },
    {
      title: "4. Steward Agent Privacy & Identity Wallet",
      items: [
        "Built standard into all autonomous Steward agents (shadenet/wallet.py).",
        "Monero (XMR) stealth subaddress generator (8...) and local encrypted transaction ledger.",
        "Zero-Knowledge ID vault storing DMV credentials and generating disposable mathematical age presentations.",
        "Interactive Operator Steward commands: !status, !wallet, !scrape, and key rotation."
      ]
    },
    {
      title: "5. Decentralized Editorial Zine (Umwelt Horizons)",
      items: [
        "6-stage compiler reading Markdown vaults with wikilinks ([[room-name]]) into an Adaptive Viewport Resolution (AVR) graph.",
        "Dynamic relation mapping linking reviews and articles to specific venue stages and shows.",
        "Automated risograph printable broadside sheet generator for physical street distribution."
      ]
    },
    {
      title: "6. Hardened Infrastructure & Darknet Routing",
      items: [
        "Single public ingress reverse proxy (Caddy TLS on 80/443), with zero internal databases or RPC ports exposed.",
        "Tor v3 Onion hidden services for web, Matrix Synapse chat, and Monero RPC.",
        "Monero transaction broadcasts routed through Tor SOCKS5 proxy via Dandelion++ to prevent ISP/IP correlation.",
        "Turnkey production deployment stack with LUKS2 AES-512 encryption at rest, WireGuard VPN, and Unbound DoT DNS."
      ]
    },
    {
      title: "7. Passkeys (WebAuthn / FIDO2) & No-Tracker Contributions",
      items: [
        "TouchID, FaceID, and hardware YubiKey passwordless authentication for human operators.",
        "One-time non-recurring Stripe contributions toward network costs.",
        "Anonymous Monero donation box for tracker-free contributions."
      ]
    }
  ];

  const currentSection = h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-4)", marginTop: "var(--nc-space-6)" } },
    h("div", {},
      h("h2.nc-h2", {}, "⚡ What Alpha v1 Can Do Right Now"),
      h("p.nc-muted", {}, "Every feature listed below is fully implemented, verified with 159 green tests, and active in the live deployment:")
    ),
    h("div.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-4)" } },
      ...currentCapabilities.map(cap =>
        h("article.nc-card-panel", {
          style: {
            padding: "var(--nc-space-4)",
            borderRadius: "var(--nc-radius-md)",
            border: "1px solid var(--nc-color-border)",
            background: "var(--nc-color-surface)",
            display: "grid",
            gap: "var(--nc-space-2)"
          }
        },
          h("h3.nc-h3", { style: { fontSize: "1.05rem" } }, cap.title),
          h("ul", { style: { paddingLeft: "1.25rem", display: "grid", gap: "0.35rem" } },
            ...cap.items.map(item => h("li", { style: { fontSize: "0.9rem", lineHeight: "1.45" } }, item))
          )
        )
      )
    )
  );

  // Section 2: What We Hope It Can Do (Roadmap)
  const roadmapItems = [
    {
      title: "1. Dedicated Hardware NFC Tap Terminals for Venues",
      desc: "Expanding beyond camera QR scanning to low-cost ($35 Raspberry Pi / USB NFC) hardware readers at bar doors so patrons can simply tap their phone without opening an app."
    },
    {
      title: "2. Autonomous A2A Ticket Exchange & Anonymous Bar Tabs",
      desc: "Equipping patron Steward agents to negotiate peer-to-peer ticket transfers and settle bar drinks directly using Monero stealth subaddresses, eliminating credit card processing fees."
    },
    {
      title: "3. Multi-City Regional Federation",
      desc: "Federating the Oak database architecture beyond Santa Rosa into neighboring Northern California music communities (Petaluma, Sebastopol, San Francisco, Oakland) across decentralized nodes."
    },
    {
      title: "4. Off-Grid LoRa & Bluetooth Mesh Relays",
      desc: "Allowing door scanners and zine updates to sync during packed festivals and cellular blackouts using decentralized local radio mesh packets."
    },
    {
      title: "5. Physical Indie Distribution Network",
      desc: "Automated distribution pipeline delivering risograph print broadsides of Umwelt Horizons to downtown record stores, indie coffeehouses, and venue corkboards."
    },
    {
      title: "6. Direct-to-Artist Royalty Splits",
      desc: "Enabling local venues to programmatically route a percentage of door covers and custom merchandise sales directly to performing musicians' private wallets."
    }
  ];

  const roadmapSection = h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-4)", marginTop: "var(--nc-space-6)" } },
    h("div", {},
      h("h2.nc-h2", {}, "🔭 What We Hope It Should Be Able to Do (Roadmap)"),
      h("p.nc-muted", {}, "The future horizon of decentralized culture, autonomous agent cooperation, and venue technology:")
    ),
    h("div", {
      style: {
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 18rem), 1fr))",
        gap: "var(--nc-space-4)"
      }
    },
      ...roadmapItems.map(item =>
        h("article.nc-card-panel", {
          style: {
            padding: "var(--nc-space-4)",
            borderRadius: "var(--nc-radius-md)",
            border: "1px solid var(--nc-color-border)",
            background: "var(--nc-color-surface)",
            display: "grid",
            gap: "var(--nc-space-2)"
          }
        },
          h("h3.nc-h3", { style: { fontSize: "1rem", color: "var(--nc-color-accent)" } }, item.title),
          h("p.nc-muted", { style: { fontSize: "0.88rem", lineHeight: "1.5" } }, item.desc)
        )
      )
    )
  );

  // Section 3: Changelog
  const changelogEntries = [
    {
      version: "Alpha v1.0.0 (v0.1.0-alpha.1)",
      date: "October 10, 2026",
      tag: "Initial Public Alpha Release",
      notes: [
        "Launched unified 3-way Zero-Knowledge age verification engine (CA DMV mDL, ZK-Passport, Ed25519 delegations).",
        "Deployed Bar Door Camera Scanner PWA (/door-scanner/) with real-time audio chime, vibration feedback, and admission tally.",
        "Equipped Steward agents standard with privacy wallet (shadenet/wallet.py) supporting Monero stealth payments and ZK ID vault.",
        "Integrated Tor daemon with v3 Onion services for web, Matrix Synapse, and Monero RPC; enabled Monero SOCKS5 transaction anonymization.",
        "Architected turnkey multi-container production deployment stack featuring LUKS2 AES-512 encryption at rest, WireGuard VPN, and Unbound DoT DNS.",
        "Redesigned contribution page (/donate/) for one-time Stripe contributions to network costs and anonymous Monero donations.",
        "Completed 159 green test suite verifying zero PII leakage, signature verification, and error recovery."
      ]
    }
  ];

  const changelogSection = h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-4)", marginTop: "var(--nc-space-6)" } },
    h("div", {},
      h("h2.nc-h2", {}, "📜 Changelog"),
      h("p.nc-muted", {}, "Chronological release history of the ShadeNet & NightCal platform:")
    ),
    h("div.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-4)" } },
      ...changelogEntries.map(entry =>
        h("article.nc-card-panel", {
          style: {
            padding: "var(--nc-space-5)",
            borderRadius: "var(--nc-radius-lg)",
            border: "1px solid var(--nc-color-border)",
            background: "var(--nc-color-surface)",
            display: "grid",
            gap: "var(--nc-space-3)"
          }
        },
          h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: "0.5rem" } },
            h("h3.nc-h3", { style: { fontSize: "1.2rem", fontWeight: "800" } }, entry.version),
            h("span.nc-muted", { style: { fontSize: "0.85rem" } }, entry.date)
          ),
          h("div", {
            style: {
              display: "inline-block",
              background: "rgba(245, 158, 11, 0.15)",
              color: "var(--nc-color-accent)",
              padding: "0.15rem 0.6rem",
              borderRadius: "4px",
              fontSize: "0.8rem",
              fontWeight: "600",
              width: "fit-content"
            }
          }, entry.tag),
          h("ul", { style: { paddingLeft: "1.25rem", display: "grid", gap: "0.4rem" } },
            ...entry.notes.map(note => h("li", { style: { fontSize: "0.9rem", lineHeight: "1.5" } }, note))
          )
        )
      )
    )
  );

  root.append(hero, currentSection, roadmapSection, changelogSection);
  return root;
}

const app = document.getElementById("app");
if (app) {
  app.replaceChildren(siteHeader(), changelogPage(), siteFooter());
}
