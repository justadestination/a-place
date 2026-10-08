// "/landing/" and its three options. These are proposals for the owner to
// choose from (see docs/LANDING_OPTIONS.md); none replaces "/" until chosen.
// All three use only existing components and tokens.
import { h } from "../core/dom.js";
import "../core/theme.js";
import { SITE } from "../core/site.js";
import { loadCalendar, filterEvents } from "../data/calendar.js";
import { loadZine, graphScene } from "../data/graph.js";
import { weekScene } from "../data/scene.js";
import { relative } from "../data/dates.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";
import { button } from "../../components/button/button.js";
import { eventRow } from "../../components/event-row/event-row.js";
import { calendarWeek } from "../../components/calendar-week/calendar-week.js";
import { zineCard } from "../../components/zine-card/zine-card.js";

const variant = document.body.dataset.variant || "";
const app = document.getElementById("app");
const model = await loadCalendar();
const upcoming = filterEvents(model, { scope: "nights" }).filter(e => e.date >= model.today);
const soonest = upcoming.slice(0, 3);
const firstDate = soonest[0]?.date;
const whenLabel = firstDate ? relative(firstDate, model.today) : "";
const toEvent = e => { location.href = `/?date=${e.detail.id ? model.eventsById.get(e.detail.id)?.date : e.detail.date}${e.detail.id ? `&event=${encodeURIComponent(e.detail.id)}` : ""}`; };
const what = `${SITE.name} lists live music, comedy, shows and trivia in ${SITE.place}, and every listing says where it came from.`;
const banner = h("p.nc-muted", {}, h("strong", {}, "Proposal. "), "One of three landing options for the owner to choose between. ", h("a", { href: "/landing/" }, "Compare all three"), ".");

async function zinePreview() {
  const zine = await loadZine();
  const g = graphScene(zine, { dims: 2 });
  return g.nodes.filter(n => n.html).slice(0, 2).map(n => zineCard(n));
}

const layouts = {
  // A — Tonight first: the answer before the explanation.
  async a() {
    const list = h("ol.nc-day-agenda__list", { role: "list" }, soonest.map(e => h("li", {}, eventRow(e))));
    list.addEventListener("nc-select", toEvent);
    return [
      banner,
      h("section.nc-landing__hero", { "aria-labelledby": "hero" },
        h("p.nc-eyebrow", {}, SITE.place),
        h("h1.nc-h1", { id: "hero" }, firstDate ? `Next up: ${whenLabel.toLowerCase() === "tonight" ? "tonight" : whenLabel}` : "What's on downtown"),
        h("p.nc-lede", {}, what),
        soonest.length ? list : h("p", {}, "Nothing is listed yet."),
        h("div.nc-cluster", {}, button({ label: "See the full calendar", variant: "primary", href: "/" }), h("a.nc-link", { href: "/zine/" }, "Or read the zine"))),
    ];
  },
  // B — Two doors: one sentence, then two equal choices.
  async b() {
    const week = calendarWeek(weekScene(model, { date: model.today }), {});
    week.addEventListener("nc-select", toEvent);
    return [
      banner,
      h("section.nc-landing__hero", { "aria-labelledby": "hero" },
        h("h1.nc-h1", { id: "hero" }, `Nights out in ${SITE.place}`),
        h("p.nc-lede", {}, what)),
      h("div.nc-landing__doors", {},
        h("section.nc-door", { "aria-labelledby": "door-cal" },
          h("h2", { id: "door-cal" }, "The calendar"),
          h("p", {}, `${upcoming.length} shows coming up. Pick a night to see who is playing and where.`),
          week,
          button({ label: "Open the calendar", variant: "primary", href: "/" })),
        h("section.nc-door", { "aria-labelledby": "door-zine" },
          h("h2", { id: "door-zine" }, `The ${SITE.zineName} zine`),
          h("p", {}, "Reviews, articles and letters about these rooms and shows, mapped by what they link to."),
          ...(await zinePreview()),
          button({ label: "Read the zine", variant: "secondary", href: "/zine/" }))),
    ];
  },
  // C — Three steps: a numbered path for people who have never been here.
  async c() {
    const list = h("ol.nc-day-agenda__list", { role: "list" }, soonest.slice(0, 2).map(e => h("li", {}, eventRow(e))));
    list.addEventListener("nc-select", toEvent);
    return [
      banner,
      h("section.nc-landing__hero", { "aria-labelledby": "hero" },
        h("h1.nc-h1", { id: "hero" }, `${SITE.name}, in three steps`),
        h("p.nc-lede", {}, what)),
      h("ol.nc-steps", { role: "list" },
        h("li.nc-step", {}, h("div", {}, h("h2", {}, "See what's on"), h("p", {}, firstDate ? `The next shows are ${whenLabel.toLowerCase() === "tonight" ? "tonight" : `on ${whenLabel}`}.` : "The calendar updates itself from the downtown listings."), list, button({ label: "Open the calendar", variant: "primary", href: "/" }))),
        h("li.nc-step", {}, h("div", {}, h("h2", {}, "Read about the rooms"), h("p", {}, `The ${SITE.zineName} zine writes about these shows. Its map shows what links to what.`), h("a.nc-link", { href: "/zine/" }, "Read the zine"))),
        h("li.nc-step", {}, h("div", {}, h("h2", {}, "Put it on your own site"), h("p", {}, "Any view here works as an embed: one line of code, sized to fit, in your colours."), h("a.nc-link", { href: "/system/#embeds" }, "Get the embed code")))),
    ];
  },
  // Chooser
  async ""() {
    const opt = (key, title, body, best) => h("li.nc-door", {},
      h("h2", {}, h("a.nc-link", { href: `/landing/${key}/` }, title)),
      h("p", {}, body),
      h("p.nc-muted", {}, h("strong", {}, "Best if: "), best));
    return [
      h("section.nc-landing__hero", { "aria-labelledby": "hero" },
        h("p.nc-eyebrow", {}, "For the owner"),
        h("h1.nc-h1", { id: "hero" }, "Pick a front door"),
        h("p.nc-lede", {}, "Three ways to orient a first-time visitor in under ten seconds: what this is, the calendar, the zine, and what to do next. Each is a working page with live data. The calendar stays at / until one is chosen.")),
      h("ul.nc-options", { role: "list" },
        opt("a", "A · Tonight first", "Opens on the next three shows, with one primary button to the full calendar. The explanation is one sentence under the headline.", "most visitors arrive asking \"what's on tonight?\""),
        opt("b", "B · Two doors", "One sentence on what NightCal is, then the calendar and the zine side by side as equals, each with a live preview.", "the zine should get equal billing with the calendar."),
        opt("c", "C · Three steps", "A numbered path: see what's on, read about the rooms, embed it on your own site.", "venues and promoters who might embed it are a key audience.")),
    ];
  },
};

const main = h("main.nc-container.nc-page.nc-landing", { id: "main", tabindex: "-1" }, ...(await layouts[variant]()));
app.replaceChildren(siteHeader(), main, siteFooter({ notes: model.notes, source: model.source }));
