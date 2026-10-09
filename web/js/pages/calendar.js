// "/" — the redesigned calendar. Billboard first: the chosen night, big;
// the week strip and two filters above it; the month below the fold (lazy).
// State lives in the URL (?date, ?scope, ?venue, ?event) so every view is shareable.
import { h, params, setParam } from "../core/dom.js";
import "../core/theme.js";
import { loadCalendar, filterEvents, roomsWithEvents, kindsWithEvents, nextDateWithEvents, KINDS } from "../data/calendar.js";
import { weekScene, dayScene, monthScene } from "../data/scene.js";
import { addDays, isValidDate, label, relative } from "../data/dates.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";
import { filterBar } from "../../components/filter-bar/filter-bar.js";
import { calendarWeek } from "../../components/calendar-week/calendar-week.js";
import { dayAgenda } from "../../components/day-agenda/day-agenda.js";
import { SITE } from "../core/site.js";
import { applyStewardPersonalization, loadStewardStub } from "../data/steward.js";

const app = document.getElementById("app");
const rawModel = await loadCalendar();
const q = params();
const stewardEnabled = q.get("steward") === "1" || window.__STEWARD_ENABLED__ === true;
let stewardPayload = null;
if (stewardEnabled) {
  stewardPayload = window.__STEWARD_PAYLOAD__ || await loadStewardStub();
}
const model = applyStewardPersonalization(rawModel, stewardPayload, { enabled: stewardEnabled });
const pathDay = location.pathname.match(/\/day\/(\d{4}-\d{2}-\d{2})/);
const initialDate = isValidDate(q.get("date"))
  ? q.get("date")
  : (document.body.dataset.date && isValidDate(document.body.dataset.date))
    ? document.body.dataset.date
    : (pathDay && isValidDate(pathDay[1]))
      ? pathDay[1]
      : model.today;

const state = {
  date: initialDate,
  scope: q.get("scope") === "all" ? "all" : "nights",
  venueId: model.venuesById.has(q.get("venue")) ? q.get("venue") : "",
  kind: KINDS[q.get("kind")] ? q.get("kind") : (KINDS[q.get("tag")] ? q.get("tag") : ""),
  month: "",
};
state.month = state.date.slice(0, 7);
const noun = () => (state.scope === "all" ? "listing" : "show");

// --- layout --------------------------------------------------------------
const controls = h("div.nc-cal__controls", {});
const week = h("div.nc-cal__week", {});
const agenda = h("div.nc-cal__agenda", { "aria-live": "polite", "aria-atomic": "false" });
const monthSlot = h("section.nc-cal__month.nc-lazy", { "aria-label": "Plan ahead" });
const main = h("main.nc-container.nc-page.nc-cal", { id: "main", tabindex: "-1" }, controls, week, agenda, monthSlot);
const footer = siteFooter({ notes: model.notes, source: model.source });
app.replaceChildren(siteHeader(), main, footer);

function drawControls() {
  controls.replaceChildren(filterBar({
    scope: state.scope,
    venueId: state.venueId,
    kind: state.kind,
    rooms: roomsWithEvents(model, { scope: "all" }),
    kinds: kindsWithEvents(model, { scope: "all" }),
  }));
}
function drawWeek() {
  week.replaceChildren(calendarWeek(weekScene(model, state), { noun: noun() }));
}
import { hubLayout } from "../../components/hub-layout/hub-layout.js";

function drawAgenda() {
  const day = dayScene(model, state);
  const filtered = filterEvents(model, state);
  const next = day.events.length ? "" : nextDateWithEvents(filtered, addDays(state.date, 1));
  const heroAgenda = dayAgenda(day, { today: model.today, noun: noun(), level: 1 });
  if (next) heroAgenda.append(h("div.nc-cal__next", {}, dayAgenda(dayScene(model, { ...state, date: next }), { today: model.today, noun: noun(), level: 2 })));
  
  agenda.replaceChildren(hubLayout({
    heroNode: heroAgenda,
    zine: null,
    summary: null,
    inbox: null,
    market: null,
  }));
  document.title = `${relative(state.date, model.today)} — ${SITE.name}, ${SITE.place}`;
}
let monthModule = null;
function drawMonth(focusDate) {
  if (!monthModule) return;
  monthSlot.replaceChildren(monthModule.calendarMonth(monthScene(model, { ...state, month: state.month }), { focusDate, noun: noun() }));
  if (focusDate) monthSlot.querySelector(`[data-date="${focusDate}"]`)?.focus();
}
function drawAll() { drawWeek(); drawAgenda(); drawMonth(); }

function syncUrl() {
  const isArchiveOrToday = location.pathname.startsWith("/day/") || location.pathname.startsWith("/today");
  if (isArchiveOrToday) {
    const targetPath = state.date === model.today ? "/today/" : `/day/${state.date}/`;
    const url = new URL(location.href);
    url.pathname = targetPath;
    url.searchParams.delete("date");
    if (state.scope && state.scope !== "nights") url.searchParams.set("scope", state.scope); else url.searchParams.delete("scope");
    if (state.venueId) url.searchParams.set("venue", state.venueId); else url.searchParams.delete("venue");
    if (state.kind) url.searchParams.set("kind", state.kind); else url.searchParams.delete("kind");
    history.pushState(null, "", url.toString());
  } else {
    setParam("date", state.date === model.today ? "" : state.date);
    setParam("scope", state.scope === "nights" ? "" : state.scope);
    setParam("venue", state.venueId);
    setParam("kind", state.kind);
  }
}

window.addEventListener("popstate", () => {
  const curQ = params();
  const curPathDay = location.pathname.match(/\/day\/(\d{4}-\d{2}-\d{2})/);
  const curDate = isValidDate(curQ.get("date"))
    ? curQ.get("date")
    : (curPathDay && isValidDate(curPathDay[1]))
      ? curPathDay[1]
      : (document.body.dataset.date && isValidDate(document.body.dataset.date))
        ? document.body.dataset.date
        : model.today;
  state.date = curDate;
  state.month = curDate.slice(0, 7);
  state.scope = curQ.get("scope") === "all" ? "all" : "nights";
  state.venueId = model.venuesById.has(curQ.get("venue")) ? curQ.get("venue") : "";
  state.kind = KINDS[curQ.get("kind")] ? curQ.get("kind") : "";
  drawControls();
  drawAll();
});

function selectDate(date, { focus } = {}) {
  state.date = date;
  state.month = date.slice(0, 7);
  syncUrl();
  drawAll();
  if (focus === "week") week.querySelector(`[data-date="${date}"]`)?.focus();
  if (focus === "agenda") agenda.querySelector("h1")?.focus();
}

// --- events from components ---------------------------------------------
controls.addEventListener("nc-filter", e => {
  state.scope = e.detail.scope;
  state.venueId = e.detail.venueId;
  state.kind = e.detail.kind || "";
  syncUrl();
  drawAll();
});
week.addEventListener("nc-shift", e => {
  selectDate(addDays(state.date, 7 * e.detail.delta));
  week.querySelector(`.nc-week__nav button:${e.detail.delta < 0 ? "first-of-type" : "last-of-type"}`)?.focus();
});
week.addEventListener("nc-select", e => { if (e.detail.kind === "day") selectDate(e.detail.date, { focus: "week" }); });
agenda.addEventListener("nc-select", e => {
  if (e.detail.kind === "event") openEvent(e.detail.id);
  if (e.detail.kind === "day") selectDate(e.detail.date, { focus: "agenda" });
});
monthSlot.addEventListener("nc-select", e => {
  if (e.detail.kind !== "day") return;
  selectDate(e.detail.date);
  drawMonth(e.detail.date);
  agenda.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
});
monthSlot.addEventListener("nc-shift", e => {
  const [y, m] = state.month.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 + e.detail.delta, 1));
  state.month = d.toISOString().slice(0, 7);
  drawMonth(e.detail.focusDate);
});

// --- event detail dialog (code-split) ----------------------------------------
let dialog = null;
async function openEvent(id, { push = true } = {}) {
  const ev = model.eventsById.get(id);
  if (!ev) return;
  const { eventCard } = await import("../../components/event-card/event-card.js");
  if (!dialog) {
    dialog = h("dialog.nc-dialog", { "aria-label": "Event details" });
    dialog.addEventListener("close", () => setParam("event", ""));
    dialog.addEventListener("click", e => { if (e.target === dialog) dialog.close(); });
    document.body.append(dialog);
  }
  const close = h("button.nc-button.nc-button--ghost.nc-dialog__close", { type: "button", onclick: () => dialog.close() }, "Close");
  dialog.setAttribute("aria-label", ev.title);
  dialog.replaceChildren(h("div.nc-dialog__inner", {}, close, eventCard(ev, { venue: model.venuesById.get(ev.venueId), today: model.today })));
  if (push) setParam("event", id);
  if (!dialog.open) dialog.showModal();
  close.focus();
}

// --- month below the fold: load its code when it is about to be seen -------
new IntersectionObserver((entries, obs) => {
  if (!entries.some(e => e.isIntersecting)) return;
  obs.disconnect();
  import("../../components/calendar-month/calendar-month.js").then(mod => { monthModule = mod; drawMonth(); });
}, { rootMargin: "400px" }).observe(monthSlot);
monthSlot.append(h("p.nc-muted", {}, label.monthYear(state.month)));

drawControls();
drawWeek();
drawAgenda();
if (q.get("event")) openEvent(q.get("event"), { push: false });
