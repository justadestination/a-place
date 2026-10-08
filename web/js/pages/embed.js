// Runtime for every /embed/<component>/ route. The page HTML names the
// component in <body data-component>; this loads only that component's module
// (code-split), renders it from query params, and starts the iframe bridge.
import { h } from "../core/dom.js";
import { startEmbed, select } from "../core/frame.js";
import { loadCalendar } from "../data/calendar.js";
import { loadZine } from "../data/graph.js";

const name = document.body.dataset.component;
const root = document.getElementById("app");
const params = new URLSearchParams(location.search);
const ctx = { calendar: () => loadCalendar(), zine: () => loadZine(), select, params };

try {
  const mod = await import(`../../components/${name}/${name}.js`);
  const el = await mod.embed(params, ctx);
  // Inside its own frame the component is the page: give it a main landmark and a name.
  const title = document.title.split(" · ")[0];
  root.replaceChildren(h("main.nc-embed-root", { "aria-label": title }, h("h1.nc-sr-only", {}, `NightCal: ${title}`), el));
  // Anything the reader picks inside the frame is reported to the host page.
  root.addEventListener("nc-select", async e => {
    if (e.detail.kind === "event") {
      const model = await loadCalendar();
      const ev = model.eventsById.get(e.detail.id);
      select("event", e.detail.id, { url: ev?.url || "", label: ev?.title || "" });
      // Rows open the full card in a dialog inside the frame; ?open=0 leaves it to the host.
      if (params.get("open") !== "0") openEvent(e.detail.id);
    } else if (e.detail.kind === "day") {
      select("day", e.detail.date);
    }
  });
} catch (err) {
  console.error(err);
  root.replaceChildren(h("p.nc-embed-root", { role: "alert" }, "This view could not load."));
}
startEmbed(name);

async function openEvent(id) {
  const [{ eventCard }, model] = await Promise.all([import("../../components/event-card/event-card.js"), loadCalendar()]);
  const ev = model.eventsById.get(id);
  if (!ev) return;
  let dlg = document.getElementById("nc-embed-dialog");
  if (!dlg) {
    dlg = h("dialog.nc-dialog", { id: "nc-embed-dialog", "aria-label": "Event details" });
    dlg.addEventListener("click", e => { if (e.target === dlg) dlg.close(); });
    document.body.append(dlg);
  }
  const close = h("button.nc-button.nc-button--ghost.nc-dialog__close", { type: "button", onclick: () => dlg.close() }, "Close");
  dlg.replaceChildren(h("div.nc-dialog__inner", {}, close, eventCard(ev, { venue: model.venuesById.get(ev.venueId), today: model.today, level: 2 })));
  dlg.showModal();
}
