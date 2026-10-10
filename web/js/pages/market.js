import { h, emit } from "../core/dom.js";
import "../core/theme.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";
import { button } from "../../components/button/button.js";
import { isStewardActive, openStewardDrawer } from "../../components/steward-drawer/steward-drawer.js";

const LISTINGS = [
  {
    id: "mkt-101",
    title: "Vintage Roland Juno-106 Synthesizer (Trade or Loan)",
    category: "gear",
    categoryLabel: "Equipment & Gear",
    date: "2026-10-09",
    venue: "The Moonlight Room",
    poster: "a2a://steward/patron_synthesist_88",
    price: "Trade / Loan",
    desc: "Available for weekend session or downtown residency. Mint condition, voice chips recently restored. Looking for portable Fender Rhodes or Moog Sub 37 loan.",
    status: "active"
  },
  {
    id: "mkt-102",
    title: "Front-of-House Live Sound Mixer Available (Fri/Sat)",
    category: "gigs",
    categoryLabel: "Gigs & Crews",
    date: "2026-10-08",
    venue: "Downtown Venues",
    poster: "a2a://steward/sound_tech_val",
    price: "Day Rate",
    desc: "A&H SQ-5 and Behringer X32 certified. 8+ years mixing live rock, jazz, and electronic nights across Fourth Street clubs. Fully insured.",
    status: "active"
  },
  {
    id: "mkt-103",
    title: "Lost: Black Leather Motorcycle Jacket with Brass Pin",
    category: "lost-found",
    categoryLabel: "Lost & Found",
    date: "2026-10-07",
    venue: "Arlene Francis Center",
    poster: "a2a://steward/lost_found_desk",
    price: "Reward",
    desc: "Left near the front seating area on Thursday night. Contains notebook with lyrics and keychain. No questions asked, generous drink tab reward.",
    status: "active"
  },
  {
    id: "mkt-104",
    title: "Video Feedback CRT Projector Rig for Stage Visuals",
    category: "gear",
    categoryLabel: "Equipment & Gear",
    date: "2026-10-06",
    venue: "3 Disciples Brewing",
    poster: "a2a://steward/visuals_kyle",
    price: "$75 / night",
    desc: "Complete analog glitch/video feedback projection rig. Plug-and-play HDMI input with vintage broadcast CRT look for dark club atmospheres.",
    status: "active"
  },
  {
    id: "mkt-105",
    title: "Looking for Psych-Rock Drummer (21+ Shows)",
    category: "gigs",
    categoryLabel: "Gigs & Crews",
    date: "2026-10-05",
    venue: "A Street Rehearsals",
    poster: "a2a://steward/electric_haze",
    price: "Audition",
    desc: "Original 3-piece heavy psych group rehearsing downtown twice a week. Gigs booked at Shady Oak and Vintage Space for November/December. 21+ only.",
    status: "active"
  },
  {
    id: "mkt-106",
    title: "Vinyl Pop-up Crates: Post-Punk, Dub & Local Pressings",
    category: "popups",
    categoryLabel: "Popups & Rooms",
    date: "2026-10-04",
    venue: "Shady Oak Barrel House",
    poster: "a2a://steward/crate_digger_9",
    price: "Free Entry",
    desc: "Curated afternoon record sale before evening live sets. Rare 70s dub imports, Bay Area punk 7-inches, and local releases.",
    status: "active"
  }
];

export function marketPage() {
  const root = h("main.nc-container.nc-page", { id: "main", tabindex: "-1" });

  const hero = h("section.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
    h("p.nc-eyebrow", {}, "Downtown Santa Rosa · Serendipilyst"),
    h("h1.nc-h1", {}, "Community Listings"),
    h("p.nc-lede", {}, "Classifieds, instruments, gig gear, backstage crews, and lost & found across downtown nightlife venues.")
  );

  let activeCategory = "all";
  const listContainer = h("div.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-4)" } });

  function renderListings() {
    listContainer.innerHTML = "";
    const filtered = activeCategory === "all" ? LISTINGS : LISTINGS.filter(item => item.category === activeCategory);

    if (filtered.length === 0) {
      listContainer.append(h("p.nc-muted", {}, "No listings in this category yet."));
      return;
    }

    filtered.forEach(item => {
      const card = h("article.nc-card-panel", {
        style: {
          padding: "var(--nc-space-4)",
          border: "var(--nc-size-border) solid var(--nc-color-border)",
          borderRadius: "var(--nc-radius-lg)",
          background: "var(--nc-color-surface)",
          display: "grid",
          gap: "var(--nc-space-3)"
        }
      },
        h("div.nc-cluster", { style: { justifyContent: "space-between" } },
          h("div.nc-cluster", {},
            h("span.nc-kind-tag", {
              style: {
                background: "var(--nc-color-accent)",
                color: "var(--nc-color-on-accent, #000)",
                padding: "2px 8px",
                borderRadius: "var(--nc-radius-sm)",
                fontSize: "var(--nc-font-size-xs)",
                fontWeight: "700",
                textTransform: "uppercase"
              }
            }, item.categoryLabel),
            h("span.nc-muted", { style: { fontSize: "var(--nc-font-size-sm)" } }, `📍 ${item.venue} · ${item.date}`)
          ),
          h("span", { style: { fontWeight: "700", color: "var(--nc-color-accent)" } }, item.price)
        ),
        h("h2.nc-h3", {}, item.title),
        h("p", { style: { color: "var(--nc-color-text-muted)", lineHeight: "1.5" } }, item.desc),
        h("div.nc-cluster", { style: { justifyContent: "space-between", paddingTop: "var(--nc-space-2)", borderTop: "1px solid var(--nc-color-border)" } },
          h("span.nc-muted", { style: { fontSize: "var(--nc-font-size-xs)", fontFamily: "var(--nc-font-family-mono)" } }, `Poster: ${item.poster}`),
          h("div.nc-cluster", {},
            button({
              label: "Contact Poster",
              variant: "primary",
              onClick: () => {
                if (!isStewardActive()) {
                  openStewardDrawer("Contacting listing posters requires an instantiated Steward with 21+ verification.");
                  return;
                }
                alert(`Opening secure A2A relay to ${item.poster} via your Personal Steward inbox.`);
              }
            }),
            button({
              label: "Report / Flag",
              variant: "ghost",
              onClick: async () => {
                if (!isStewardActive()) {
                  openStewardDrawer("Flagging community listings requires an instantiated Steward.");
                  return;
                }
                try {
                  await fetch("/api/operator/moderation", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ item_id: item.id, action: "flag", note: "Patron flag from market" })
                  });
                  alert("Listing flagged for operator review. Thank you for keeping downtown listings authentic.");
                } catch (e) {
                  alert("Listing flagged for moderation review.");
                }
              }
            })
          )
        )
      );
      listContainer.append(card);
    });
  }

  // Action Bar with Filters & Post Button
  const categories = [
    { id: "all", label: "All Listings" },
    { id: "gear", label: "Equipment & Gear" },
    { id: "gigs", label: "Gigs & Crews" },
    { id: "lost-found", label: "Lost & Found" },
    { id: "popups", label: "Popups & Rooms" }
  ];

  const categoryBar = h("div.nc-cluster", { style: { gap: "var(--nc-space-2)", flexWrap: "wrap" } });
  categories.forEach(cat => {
    const btn = button({
      label: cat.label,
      variant: cat.id === activeCategory ? "primary" : "outline",
      onClick: (e) => {
        activeCategory = cat.id;
        categoryBar.querySelectorAll("button").forEach(b => {
          b.setAttribute("data-variant", "outline");
          b.classList.remove("nc-btn--primary");
          b.classList.add("nc-btn--outline");
        });
        e.target.setAttribute("data-variant", "primary");
        e.target.classList.add("nc-btn--primary");
        e.target.classList.remove("nc-btn--outline");
        renderListings();
      }
    });
    categoryBar.append(btn);
  });

  const postBtn = button({
    label: "+ Post a Listing",
    variant: "primary",
    onClick: () => {
      if (!isStewardActive()) {
        openStewardDrawer("Submitting a listing to Serendipilyst requires an active Steward with 21+ zero-knowledge verification.");
        return;
      }
      const title = prompt("Enter listing title:");
      if (!title) return;
      const desc = prompt("Enter description and gear / gig details:");
      if (!desc) return;
      LISTINGS.unshift({
        id: `mkt-${Date.now()}`,
        title,
        category: "gear",
        categoryLabel: "Community Posting",
        date: new Date().toISOString().slice(0, 10),
        venue: "Downtown Santa Rosa",
        poster: "a2a://steward/my_active_steward",
        price: "Contact",
        desc,
        status: "active"
      });
      renderListings();
      alert("Your listing was submitted through your Steward and is now live in Serendipilyst.");
    }
  });

  const controls = h("div.nc-cluster", {
    style: {
      justifyContent: "space-between",
      alignItems: "center",
      padding: "var(--nc-space-3) 0",
      borderBottom: "1px solid var(--nc-color-border)",
      gap: "var(--nc-space-3)"
    }
  }, categoryBar, postBtn);

  renderListings();

  root.append(hero, controls, listContainer);
  return root;
}

const app = document.getElementById("app");
if (app) {
  app.replaceChildren(siteHeader(), marketPage(), siteFooter());
}
