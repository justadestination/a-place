/**
 * WorldSum sheet for Serendipilyst.
 * The sales list does not render here. A flag stands on the map only when
 * it is listed. The pennant is American Traditional flash, and the Steward
 * says what the tackbot used to say. Bored people inside the amber ring
 * can be invited into one room.
 */

import { h, svg } from "../../js/core/dom.js";
import { button } from "../button/button.js";
import { chatView } from "../chat/chat.js";
import {
  CHARGES,
  FIELDS,
  chargeById,
  fieldById,
  flameMark,
  hearOrder,
  heartMark,
  intentIcon,
  normalizeAppearance,
  pennantSvg,
  stewardIntro,
  stewardNeedPlace,
  stewardOnCharge,
  stewardOnField,
  stewardOnList,
  stewardOnPull,
  stewardOnUpdate,
} from "./pennant.js";
import {
  VIEW,
  ANCHORS,
  PLACES,
  TRAILS,
  PEOPLE,
  YOU_ID,
  NEAR_RADIUS,
  placeById,
  boredNearby,
} from "../../js/data/worldsum.js";

const KIND = {
  you: "You",
  person: "Person",
  human: "Human flag",
  steward: "Steward flag",
  business: "Business flag",
};

const IDLE = {
  lumen: "I was watching the square. Nothing is happening.",
  jules: "The lot is empty.",
  mara: "Same over at Dark Pool.",
};

const LABEL = {
  square: { dx: 0, dy: -46, anchor: "middle", lines: ["Courthouse", "Square"] },
  rail: { dx: 0, dy: 36, anchor: "middle", lines: ["Railroad", "Square"] },
  "dark-pool": { dx: -28, dy: 4, anchor: "end" },
  lot: { dx: 22, dy: 4, anchor: "start" },
  "north-gate": { dx: 0, dy: -36, anchor: "middle" },
  "far-lake": { dx: 0, dy: 50, anchor: "middle" },
  "long-water": { dx: -28, dy: 4, anchor: "end" },
  narrows: { dx: 62, dy: 4, anchor: "start" },
  "three-pools": { dx: 0, dy: -28, anchor: "middle" },
  "east-water": { dx: 0, dy: 40, anchor: "middle" },
};

const FOREST = "M 36 250 C 24 160 90 70 210 46 C 310 28 340 70 400 58 C 500 40 560 24 650 48 C 760 78 860 60 940 120 C 990 160 1010 210 980 270 C 960 320 990 400 940 470 C 900 540 820 600 720 640 C 600 690 500 710 420 690 C 300 660 230 700 160 640 C 90 580 40 500 28 420 C 16 340 20 290 36 250 Z";

const WOODS = "M 430 40 C 520 16 640 28 720 90 C 780 140 760 220 690 260 C 600 310 490 280 440 220 C 380 160 350 80 430 40 Z";

function nameList(people) {
  const names = people.map((person) => person.name);
  if (names.length < 2) return names[0] || "";
  if (names.length === 2) return `${names[0]} and ${names[1]}`;
  return `${names.slice(0, -1).join(", ")}, and ${names[names.length - 1]}`;
}

function waterMarks(place) {
  if (place.id === "three-pools") {
    return [
      svg("circle", { class: "nc-worldsum__water", cx: place.x - 14, cy: place.y - 6, r: 8 }),
      svg("circle", { class: "nc-worldsum__water", cx: place.x + 10, cy: place.y - 8, r: 7 }),
      svg("circle", { class: "nc-worldsum__water", cx: place.x - 2, cy: place.y + 10, r: 8 }),
    ];
  }
  if (place.id === "narrows") {
    return [svg("ellipse", {
      class: "nc-worldsum__water",
      cx: place.x,
      cy: place.y,
      rx: 46,
      ry: 16,
      transform: `rotate(-18 ${place.x} ${place.y})`,
    })];
  }
  if (place.id === "long-water") {
    return [svg("ellipse", {
      class: "nc-worldsum__water",
      cx: place.x,
      cy: place.y,
      rx: 16,
      ry: 42,
    })];
  }
  return [svg("circle", { class: "nc-worldsum__water", cx: place.x, cy: place.y, r: place.r })];
}

function sheetSvg(you) {
  const trails = TRAILS.map(([fromId, toId]) => {
    const from = placeById(fromId);
    const to = placeById(toId);
    return svg("line", {
      class: "nc-worldsum__trail",
      x1: from.x,
      y1: from.y,
      x2: to.x,
      y2: to.y,
    });
  });
  const waters = PLACES.filter((place) => place.water).flatMap(waterMarks);
  const labels = PLACES.map((place) => {
    const at = LABEL[place.id] || { dx: 0, dy: 20, anchor: "middle" };
    const lines = at.lines || [place.name];
    const x = place.x + at.dx;
    const y = place.y + at.dy;
    return svg("text", {
      class: "nc-worldsum__label",
      x,
      y,
      "text-anchor": at.anchor,
    }, lines.map((line, index) => svg("tspan", { x, dy: index === 0 ? 0 : "1.15em" }, line)));
  });
  const milestones = ANCHORS.map((anchor) => svg("circle", {
    class: "nc-worldsum__milestone",
    cx: anchor.x,
    cy: anchor.y,
    r: 7,
  }));

  return svg("svg", {
    viewBox: `0 0 ${VIEW.width} ${VIEW.height}`,
    role: "img",
    "aria-labelledby": "worldsum-map-title worldsum-map-desc",
  },
    svg("title", { id: "worldsum-map-title" }, "WorldSum"),
    svg("desc", { id: "worldsum-map-desc" }, "A Nuuksio forest sheet pinned to Courthouse Square and Railroad Square. The amber ring is who is close enough to invite."),
    svg("path", { class: "nc-worldsum__forest", d: FOREST }),
    svg("path", { class: "nc-worldsum__woods", d: WOODS }),
    trails,
    waters,
    svg("circle", { class: "nc-worldsum__near", cx: you.x, cy: you.y, r: NEAR_RADIUS }),
    milestones,
    labels,
    svg("text", { class: "nc-worldsum__country", x: 48, y: 668 }, "WorldSum"),
    svg("text", { class: "nc-worldsum__sheet-note", x: 48, y: 694 }, "Nuuksio, on Santa Rosa"),
    svg("text", { class: "nc-worldsum__label", x: 948, y: 36, "text-anchor": "middle" }, "N"),
    svg("line", { class: "nc-worldsum__trail", x1: 948, y1: 44, x2: 948, y2: 72 }),
  );
}

function mark(kind, bored) {
  return h("span.nc-worldsum__mark", {
    "data-kind": kind,
    "data-bored": bored ? "true" : "false",
    "aria-hidden": "true",
  });
}

function keyItem(kind, label, bored) {
  return h("span.nc-worldsum__key-item", {}, mark(kind, bored), label);
}

export function worldsumMap() {
  const roster = PEOPLE.map((person) => ({
    ...person,
    appearance: person.appearance ? { ...person.appearance } : null,
  }));
  const you = roster.find((person) => person.id === YOU_ID);
  const home = { x: you.x, y: you.y };
  const draft = {
    field: "crimson",
    charge: "dagger",
    motto: "",
    placeId: "lot",
    line: "heavy",
    ribbon: true,
    fly: "swallowtail",
    intents: [],
    goodAt: "",
    enjoy: "",
    refuse: "",
  };
  let selectedId = YOU_ID;
  let roomOpen = false;
  let deal = null;
  const pinButtons = new Map();
  const listButtons = new Map();

  const detailKind = h("p.nc-worldsum__kind");
  const detailName = h("h2.nc-h3");
  const detailNote = h("p");
  const detail = h("div.nc-worldsum__detail", { "aria-live": "polite" }, detailKind, detailName, detailNote);
  const previewHost = h("div.nc-worldsum__preview");
  const banner = h("p.nc-worldsum__banner", { style: { background: "#0a080f", color: "#e8dcc4" }, hidden: true });
  const steward = h("p.nc-worldsum__steward", {}, stewardIntro());
  const peopleList = h("ul.nc-worldsum__people");
  const boredEmpty = h("p.nc-muted", { hidden: true }, "Nobody bored is close enough to invite.");
  const boredActions = h("div.nc-worldsum__actions");
  const pins = h("div.nc-worldsum__pins");
  const sheetSvgNode = sheetSvg(you);
  const spin = h("div.nc-worldsum__spin", {}, sheetSvgNode, pins);
  const sheet = h("div.nc-worldsum__sheet", {}, spin);
  const chatHost = h("div.nc-worldsum__chat");

  function personByRoster(id) {
    return roster.find((person) => person.id === id);
  }

  function renderDetail() {
    const person = personByRoster(selectedId);
    detailKind.textContent = KIND[person.kind] || "Person";
    detailName.textContent = person.name;
    const bored = person.bored ? "Bored." : "Not bored.";
    const look = person.appearance;
    const flash = look
      ? ` ${fieldById(look.field).name} field, ${chargeById(look.charge).name.toLowerCase()}${look.motto ? `, motto ${look.motto}` : ""}.`
      : "";
    const place = person.placeId ? placeById(person.placeId) : null;
    let listing = "";
    if (person.listed && place) listing = ` Listed at ${place.name}.`;
    else if (person.kind === "you") listing = " Not listed, so this place stays off the map.";
    const spoken = person.id === YOU_ID ? draft : person;
    const sentences = (spoken.intents || []).map((item) => item.sentence).filter(Boolean).join(" ");
    const lines = [
      spoken.goodAt ? `Good at ${spoken.goodAt}` : "",
      spoken.enjoy ? `Enjoys ${spoken.enjoy}` : "",
      spoken.refuse ? `Won't be part of ${spoken.refuse}` : "",
    ].filter(Boolean).join(" ");
    detailNote.textContent = `${bored}${flash}${listing} ${person.note}${sentences ? ` ${sentences}` : ""}${lines ? ` ${lines}` : ""}`;
  }

  function select(id) {
    selectedId = id;
    for (const [pid, pin] of pinButtons) pin.setAttribute("aria-pressed", pid === id ? "true" : "false");
    for (const [pid, pin] of listButtons) pin.setAttribute("aria-pressed", pid === id ? "true" : "false");
    renderDetail();
    renderDeal();
  }

  function pinFace(person) {
    const nodes = [];
    if (person.listed && person.appearance) {
      const holder = person.kind === "you" ? "human" : person.kind;
      nodes.push(pennantSvg(person.appearance, holder));
    } else {
      nodes.push(mark(person.kind, person.bored));
    }
    if (person.listed && person.intents && person.intents.length) {
      nodes.push(h("span.nc-worldsum__intents", { "aria-hidden": "true" }, person.intents.map((item) => intentIcon(item.kind))));
    }
    return nodes;
  }

  function paintPins() {
    pins.replaceChildren();
    pinButtons.clear();
    for (const person of roster) {
      const pin = h("button.nc-worldsum__pin", {
        type: "button",
        style: {
          left: `${(person.x / VIEW.width) * 100}%`,
          top: `${(person.y / VIEW.height) * 100}%`,
        },
        "data-side": person.side || "s",
        "data-id": person.id,
        "data-listed": person.listed ? "true" : "false",
        "aria-pressed": person.id === selectedId ? "true" : "false",
        "aria-label": `${person.name}, ${KIND[person.kind]}. ${person.listed ? "Listed. " : ""}${person.note}`,
        onclick: () => select(person.id),
      }, pinFace(person), h("span.nc-worldsum__pin-name", {}, person.label || person.name));
      pinButtons.set(person.id, pin);
      pins.append(pin);
    }
    const ring = sheetSvgNode.querySelector(".nc-worldsum__near");
    if (ring) {
      ring.setAttribute("cx", String(you.x));
      ring.setAttribute("cy", String(you.y));
    }
  }

  function paintBored() {
    const nearby = boredNearby(roster);
    peopleList.replaceChildren();
    listButtons.clear();
    for (const person of nearby) {
      const itemButton = h("button.nc-worldsum__person", {
        type: "button",
        "aria-pressed": person.id === selectedId ? "true" : "false",
        onclick: () => select(person.id),
      },
        h("span", {}, person.name),
        h("span.nc-worldsum__person-kind", {}, KIND[person.kind]),
      );
      listButtons.set(person.id, itemButton);
      peopleList.append(h("li", {}, itemButton));
    }
    peopleList.hidden = nearby.length === 0;
    boredEmpty.hidden = nearby.length !== 0;
    if (roomOpen) return;
    boredActions.replaceChildren();
    if (nearby.length) {
      boredActions.append(button({
        label: "Invite them in",
        variant: "secondary",
        onClick: openRoom,
      }));
    }
  }

  function intentList(intents) {
    return h("ul.nc-worldsum__intent-list", {}, (intents || []).map((item) => (
      h("li", {}, intentIcon(item.kind), h("span", {}, item.sentence))
    )));
  }

  function paintPreview() {
    const look = normalizeAppearance(draft);
    const lines = [];
    if (draft.intents.length) lines.push(intentList(draft.intents));
    if (draft.goodAt) lines.push(h("p.nc-worldsum__profile", {}, `Good at ${draft.goodAt}`));
    if (draft.enjoy) lines.push(h("p.nc-worldsum__profile", {}, `Enjoys ${draft.enjoy}`));
    if (draft.refuse) lines.push(h("p.nc-worldsum__profile", {}, `Won't be part of ${draft.refuse}`));
    previewHost.replaceChildren(pennantSvg(look, "human", { preview: true }), ...lines);
    banner.hidden = !look.motto;
    banner.textContent = look.motto;
  }

  function mergeProfile(profile) {
    if (!profile) return;
    for (const item of profile.intents || []) {
      draft.intents = draft.intents.filter((row) => row.kind !== item.kind);
      if (item.sentence) draft.intents.push({ kind: item.kind, sentence: item.sentence });
    }
    if (profile.good_at) draft.goodAt = profile.good_at;
    if (profile.enjoy) draft.enjoy = profile.enjoy;
    if (profile.refuse) draft.refuse = profile.refuse;
  }

  function syncControls() {
    for (const [id, btn] of swatchButtons) btn.setAttribute("aria-pressed", id === draft.field ? "true" : "false");
    charge.value = draft.charge;
    motto.value = draft.motto;
    lineSelect.value = draft.line;
    ribbonSelect.value = draft.ribbon ? "on" : "off";
    flySelect.value = draft.fly || "swallowtail";
    place.value = draft.placeId;
  }

  function tellSteward() {
    const said = order.value.trim();
    if (!said) {
      steward.textContent = "Tell me what to paint.";
      return;
    }
    let heard;
    try {
      heard = hearOrder(said, draft);
    } catch (err) {
      steward.textContent = err.message;
      return;
    }
    Object.assign(draft, heard.appearance);
    if (heard.placeId) draft.placeId = heard.placeId;
    mergeProfile(heard.profile);
    syncControls();
    paintPreview();
    order.value = "";
    if (heard.listed === true) listFlag();
    else if (heard.listed === false) pullFlag();
    steward.textContent = heard.reply;
  }

  function paintListing() {
    listBtn.querySelector("span").textContent = you.listed ? "Update the flag" : "List this flag";
    pullBtn.hidden = !you.listed;
  }

  function listFlag() {
    const place = placeById(draft.placeId);
    if (!place) {
      steward.textContent = stewardNeedPlace();
      return;
    }
    const was = you.listed;
    you.listed = true;
    you.placeId = place.id;
    you.appearance = normalizeAppearance(draft);
    you.intents = draft.intents.map((item) => ({ ...item }));
    you.goodAt = draft.goodAt;
    you.enjoy = draft.enjoy;
    you.refuse = draft.refuse;
    you.x = Math.min(VIEW.width - 40, place.x + 18);
    you.y = Math.min(VIEW.height - 48, place.y + 22);
    you.note = `Your flag, listed at ${place.name}.`;
    steward.textContent = was ? stewardOnUpdate(place.name) : stewardOnList(place.name);
    paintPins();
    paintBored();
    paintListing();
    renderDetail();
  }

  function pullFlag() {
    you.listed = false;
    you.placeId = "";
    you.x = home.x;
    you.y = home.y;
    you.note = "Not listed. This dot is only on your screen.";
    steward.textContent = stewardOnPull();
    paintPins();
    paintBored();
    paintListing();
    renderDetail();
  }

  function openRoom() {
    const nearby = boredNearby(roster);
    if (!nearby.length) return;
    roomOpen = true;
    const roomId = "!nothing:shady.example.org";
    const verb = nearby.length === 1 ? "is" : "are";
    const invited = nameList(nearby);
    const messages = [
      {
        event_id: "$m_invite",
        sender: "@steward:shady.example.org",
        content: `${invited} ${verb} in. Talk about nothing in particular.`,
        timestamp: Date.now() - 40000,
        redacted: false,
      },
      ...nearby.map((person, index) => ({
        event_id: `$m_${person.id}`,
        sender: person.name,
        content: IDLE[person.id] || `${person.name} is here.`,
        timestamp: Date.now() - 30000 + index * 1000,
        redacted: false,
      })),
    ];
    const chat = chatView({
      title: "Nothing in particular",
      heading: "h2",
      rooms: [{
        room_id: roomId,
        alias: "#nothing:shady.example.org",
        name: "Nothing in particular",
        topic: "Whoever was bored nearby.",
        kind: "domain",
      }],
      activeRoomId: roomId,
      messages,
      pseudonym: "@anon-you:shady.example.org",
    });
    boredActions.replaceChildren(h("p", {}, `${invited} ${verb} in the room.`));
    chatHost.replaceChildren(chat);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      || document.documentElement.getAttribute("data-motion") === "reduce";
    chatHost.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    chat.querySelector("#nc-chat-composer-input")?.focus();
  }

  function sentencePeriod(text) {
    const said = String(text || "").trim();
    if (!said) return "";
    return ".!?".includes(said[said.length - 1]) ? said : `${said}.`;
  }

  // The market room talks to the API as the signed-in Steward. Sample people
  // on the static sheet have no flag behind them, so they get no room.
  const SESSION_KEY = "nightcal.auth.session_token";

  function sessionToken() {
    try {
      return localStorage.getItem(SESSION_KEY) || "";
    } catch {
      return "";
    }
  }

  function authHeaders() {
    const token = sessionToken();
    const headers = { "Content-Type": "application/json" };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
      headers["X-Session-Token"] = token;
    }
    return headers;
  }

  async function dealCall(args) {
    let response;
    try {
      response = await fetch("/api/flags", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ command: "deal", args }),
      });
    } catch {
      throw new Error("I can't reach the house right now.");
    }
    let data = {};
    try {
      data = await response.json();
    } catch {
      /* keep the generic line below */
    }
    if (!response.ok || !data.ok) {
      throw new Error((data.error && (data.error.message || data.error)) || "That didn't go through.");
    }
    return data.result;
  }

  async function loadRoom() {
    if (!deal) return;
    const headers = authHeaders();
    try {
      const [who, said] = await Promise.all([
        fetch("/api/chat/auth", { headers }).then((r) => r.json()),
        fetch(`/api/chat/rooms/${encodeURIComponent(deal.roomId)}/messages?limit=200`, { headers }).then((r) => r.json()),
      ]);
      deal.pseudonym = who.pseudonym || deal.pseudonym;
      deal.messages = Array.isArray(said.messages) ? said.messages : deal.messages;
    } catch {
      /* keep what is on screen */
    }
    paintChat();
  }

  function paintChat() {
    const chat = chatView({
      title: deal.name,
      heading: "h2",
      privacy: "This room is private. Only the two of you and the Steward are in it.",
      showBridge: false,
      rooms: [{
        room_id: deal.roomId,
        alias: "#private:shady.example.org",
        name: deal.name,
        topic: deal.sentence,
        kind: "private",
      }],
      activeRoomId: deal.roomId,
      messages: deal.messages,
      pseudonym: deal.pseudonym,
      sessionToken: sessionToken(),
    });
    chatHost.replaceChildren(chat);
  }

  async function openPrivate(person) {
    const sentence = (person.intents && person.intents[0] && person.intents[0].sentence) || person.note;
    steward.textContent = "I'm telling their steward.";
    let opened;
    try {
      opened = await dealCall({ action: "interest", flag_id: person.flagId, sentence: sentencePeriod(sentence) });
    } catch (err) {
      steward.textContent = err.message;
      return;
    }
    deal = {
      personId: person.id,
      name: opened.name || person.label || person.name,
      sentence: opened.sentence,
      roomId: opened.room_id,
      stage: "talk",
      terms: null,
      messages: [],
      pseudonym: "",
    };
    steward.textContent = opened.reply;
    await loadRoom();
    renderDeal();
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      || document.documentElement.getAttribute("data-motion") === "reduce";
    chatHost.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }

  function rateRow(kind, input, readout) {
    const mark = kind === "hearts" ? heartMark() : flameMark();
    const label = kind === "hearts" ? "Hearts" : "Flames";
    return h("div.nc-worldsum__rating", {}, mark, h("span", {}, label), input, readout);
  }

  function termsLine(terms) {
    const price = `${terms.amount} ${terms.unit || ""}`.trim();
    return `${sentencePeriod(terms.item)} The price is ${price}.`;
  }

  async function readRoom() {
    if (!deal || deal.reading) return;
    deal.reading = true;
    steward.textContent = "I'm reading the room.";
    try {
      deal.terms = await dealCall({ action: "accord", step: "read", room_id: deal.roomId });
      deal.stage = "confirm";
      steward.textContent = deal.terms.reply;
    } catch (err) {
      steward.textContent = err.message;
    } finally {
      deal.reading = false;
    }
    await loadRoom();
    renderDeal();
  }

  async function confirmTerms() {
    try {
      const seen = await dealCall({ action: "accord", step: "confirm", room_id: deal.roomId, terms: deal.terms.terms });
      deal.terms = seen;
      deal.stage = seen.state === "accorded" ? "rate" : "waiting";
      steward.textContent = seen.reply;
    } catch (err) {
      steward.textContent = err.message;
      if (/terms I read last/.test(err.message)) deal.stage = "talk";
    }
    renderDeal();
  }

  function inXmr(terms) {
    return ["XMR", "MONERO"].includes(String(terms && terms.unit || "").toUpperCase());
  }

  async function takeObligation() {
    try {
      deal.obligation = await dealCall({ action: "oblige", room_id: deal.roomId, terms: deal.terms.terms });
      steward.textContent = deal.obligation.reply;
    } catch (err) {
      steward.textContent = err.message;
    }
    renderDeal();
  }

  async function obligationStep(action, tip) {
    try {
      deal.obligation = await dealCall({
        action, obligation_id: deal.obligation.id,
        ...(tip && tip.value.trim() ? { tip: tip.value.trim() } : {}),
      });
      steward.textContent = deal.obligation.reply;
    } catch (err) {
      steward.textContent = err.message;
    }
    renderDeal();
  }

  function obligationForm() {
    const ob = deal.obligation;
    if (!ob) {
      if (deal.terms.side !== "buyer") {
        return h("p", {}, "The price is in XMR. The buyer can take on the obligation to the platform.");
      }
      return h("div.nc-worldsum__deal-form", {},
        h("p", {}, `You would owe the platform ${deal.terms.amount} XMR for ${sentencePeriod(deal.terms.item)}`),
        button({ label: "Take on the obligation", variant: "secondary", attrs: { id: "nc-deal-oblige" }, onClick: takeObligation }),
      );
    }
    if (ob.state === "obliged" && deal.terms.side === "buyer") {
      const tip = h("input.nc-worldsum__control", {
        id: "nc-deal-tip", type: "text", inputmode: "decimal", "aria-label": "Tip the platform, optional",
      });
      return h("div.nc-worldsum__deal-form", {},
        h("p", {}, `You owe the platform ${ob.amount_xmr} XMR.`),
        h("label.nc-label", { for: "nc-deal-tip" }, "Tip, if you want"),
        tip,
        button({ label: "Pay", variant: "secondary", attrs: { id: "nc-deal-pay" }, onClick: () => obligationStep("pay", tip) }),
      );
    }
    if (ob.state === "paid") {
      return h("div.nc-worldsum__deal-form", {},
        h("p", {}, `Paid. ${ob.amount_xmr} XMR is with the platform.`),
        button({ label: "Release", variant: "secondary", attrs: { id: "nc-deal-release" }, onClick: () => obligationStep("release") }),
      );
    }
    if (ob.state === "released") return h("p", {}, "Released to the seller.");
    return h("p", {}, `The buyer owes the platform ${ob.amount_xmr} XMR.`);
  }

  async function sendRating(hearts, flames, word) {
    const token = word.value.trim();
    if (!token) {
      steward.textContent = "A rating needs hearts, flames, and one word.";
      return;
    }
    try {
      const done = await dealCall({
        action: "rate", room_id: deal.roomId,
        personal: Number(hearts.value), product: Number(flames.value), word: token,
      });
      deal.stage = "done";
      steward.textContent = done.reply;
    } catch (err) {
      steward.textContent = err.message;
    }
    renderDeal();
  }

  function rateForm() {
    const hearts = h("input.nc-worldsum__range", {
      id: "nc-deal-hearts", type: "range", min: "1", max: "100", value: "50",
      "aria-label": "Personal rating, hearts",
    });
    const flames = h("input.nc-worldsum__range", {
      id: "nc-deal-flames", type: "range", min: "1", max: "100", value: "50",
      "aria-label": "Product rating, flames",
    });
    const heartRead = h("span.nc-worldsum__rate-num", {}, "50");
    const flameRead = h("span.nc-worldsum__rate-num", {}, "50");
    hearts.addEventListener("input", () => { heartRead.textContent = hearts.value; });
    flames.addEventListener("input", () => { flameRead.textContent = flames.value; });
    const word = h("input.nc-worldsum__control", {
      id: "nc-deal-word", type: "text", maxlength: "24", "aria-label": "One word for the experience",
    });
    return h("div.nc-worldsum__deal-form", {},
      h("p", {}, "If you want, leave a rating. Only the Steward sees it."),
      rateRow("hearts", hearts, heartRead),
      rateRow("flames", flames, flameRead),
      h("label.nc-label", { for: "nc-deal-word" }, "One word"),
      word,
      button({
        label: "Leave the rating",
        variant: "secondary",
        attrs: { id: "nc-deal-rate" },
        onClick: () => sendRating(hearts, flames, word),
      }),
    );
  }

  function renderDeal() {
    dealHost.replaceChildren();
    const person = personByRoster(selectedId);
    if (!person || person.id === YOU_ID) return;
    const intents = person.intents || [];
    if (!deal || deal.personId !== selectedId) {
      if (!intents.length) return;
      dealHost.append(intentList(intents));
      if (!person.flagId) {
        dealHost.append(h("p.nc-muted", {}, "A sample flag. Nobody stands behind it, so there is no room to open."));
      } else if (!sessionToken()) {
        dealHost.append(h("p.nc-muted", {}, "Sign in, and your Steward can tell theirs."));
      } else {
        dealHost.append(button({
          label: "Tell their steward",
          variant: "secondary",
          attrs: { id: "nc-tell-steward" },
          onClick: () => openPrivate(person),
        }));
      }
      return;
    }
    dealHost.append(h("p", {}, `You and ${deal.name} are in the room.`));
    const refresh = button({ label: "Refresh the room", variant: "secondary", onClick: loadRoom });
    if (deal.stage === "talk") {
      dealHost.append(
        h("p", {}, "Talk it through in the room. When you have settled what changes hands and the price, ask the Steward to read it."),
        h("div.nc-worldsum__actions", {},
          refresh,
          button({ label: "Read the room", variant: "secondary", attrs: { id: "nc-accord-read" }, onClick: readRoom }),
        ),
      );
    } else if (deal.stage === "confirm") {
      dealHost.append(
        h("p", {}, termsLine(deal.terms)),
        h("div.nc-worldsum__actions", {},
          button({ label: "Yes. That is what I expect.", variant: "secondary", attrs: { id: "nc-accord-yes" }, onClick: confirmTerms }),
          button({ label: "Not quite. Keep talking.", variant: "secondary", onClick: () => { deal.stage = "talk"; renderDeal(); } }),
        ),
      );
    } else if (deal.stage === "waiting") {
      dealHost.append(
        h("p", {}, `${termsLine(deal.terms)} Their user has not confirmed yet.`),
        h("div.nc-worldsum__actions", {},
          button({ label: "Check again", variant: "secondary", attrs: { id: "nc-accord-check" }, onClick: confirmTerms }),
          button({ label: "Read the room again", variant: "secondary", onClick: readRoom }),
        ),
      );
    } else if (deal.stage === "rate") {
      dealHost.append(h("p", {}, termsLine(deal.terms)));
      if (inXmr(deal.terms)) dealHost.append(obligationForm());
      dealHost.append(rateForm());
    } else {
      if (inXmr(deal.terms)) dealHost.append(obligationForm());
      dealHost.append(h("p", {}, "Rated. Thank you."));
    }
  }

  const listBtn = button({ label: "List this flag", variant: "primary", onClick: listFlag });
  const pullBtn = button({ label: "Pull the flag", variant: "secondary", onClick: pullFlag });
  pullBtn.hidden = true;
  const tellBtn = button({ label: "Tell the Steward", variant: "secondary", type: "button", onClick: tellSteward });

  const order = h("input.nc-worldsum__control", {
    id: "nc-flag-order",
    type: "text",
    maxlength: "200",
    placeholder: "Paint it black",
    "aria-label": "Tell the Steward",
    onkeydown: (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      order.dataset.told = "1";
      tellSteward();
    },
  });

  const swatches = h("div.nc-worldsum__swatches", { role: "group", "aria-label": "Field color" });
  const swatchButtons = new Map();
  for (const field of FIELDS) {
    const swatch = h("button.nc-worldsum__swatch", {
      type: "button",
      style: { background: field.fill },
      "aria-label": `${field.name} field`,
      "aria-pressed": field.id === draft.field ? "true" : "false",
      onclick: () => {
        draft.field = field.id;
        for (const [id, btn] of swatchButtons) btn.setAttribute("aria-pressed", id === field.id ? "true" : "false");
        steward.textContent = stewardOnField(field.id);
        paintPreview();
      },
    });
    swatchButtons.set(field.id, swatch);
    swatches.append(swatch);
  }

  function detailSelect(id, label, value, choices, apply) {
    return h("select.nc-select.nc-worldsum__control", {
      id,
      "aria-label": label,
      onchange: (event) => apply(event.target.value),
    }, choices.map((item) => h("option", { value: item.id, selected: item.id === value }, item.name)));
  }

  const charge = detailSelect("nc-flag-charge", "Charge", draft.charge, CHARGES, (value) => {
    draft.charge = value;
    steward.textContent = stewardOnCharge(value);
    paintPreview();
  });

  const motto = h("input.nc-worldsum__control", {
    id: "nc-flag-motto",
    type: "text",
    maxlength: "24",
    "aria-label": "Motto, up to 24 characters",
    placeholder: "Motto",
    oninput: (event) => {
      draft.motto = event.target.value;
      paintPreview();
    },
  });

  const lineSelect = detailSelect("nc-flag-line", "Line", draft.line, [
    { id: "heavy", name: "Heavy line" },
    { id: "fine", name: "Fine line" },
  ], (value) => {
    draft.line = value;
    steward.textContent = value === "fine" ? "Fine line." : "Heavy line.";
    paintPreview();
  });

  const ribbonSelect = detailSelect("nc-flag-ribbon", "Ribbon", draft.ribbon ? "on" : "off", [
    { id: "on", name: "Ribbon on" },
    { id: "off", name: "Ribbon off" },
  ], (value) => {
    draft.ribbon = value === "on";
    steward.textContent = draft.ribbon ? "Ribbon on." : "Ribbon off.";
    paintPreview();
  });

  const flySelect = detailSelect("nc-flag-fly", "Fly", draft.fly, [
    { id: "swallowtail", name: "Swallowtail" },
    { id: "notched", name: "Notched" },
    { id: "banner", name: "Banner" },
  ], (value) => {
    draft.fly = value;
    const lines = { swallowtail: "Swallowtail.", notched: "Notched.", banner: "Banner." };
    steward.textContent = lines[value];
    paintPreview();
  });

  const place = detailSelect("nc-flag-place", "Place to list", draft.placeId, PLACES, (value) => {
    draft.placeId = value;
  });

  const workshop = h("form.nc-worldsum__workshop", {
    "aria-label": "Your flag",
    onsubmit: (event) => {
      event.preventDefault();
      if (order.dataset.told === "1") {
        delete order.dataset.told;
        return;
      }
      if (document.activeElement === order) {
        tellSteward();
        return;
      }
      listFlag();
    },
  },
    h("h2.nc-h3", {}, "Your flag"),
    h("p.nc-muted", {}, "Set the flag below, or tell the Steward in one line. An intent needs a sentence. Listing it is what puts the place on the sheet."),
    previewHost,
    banner,
    h("details.nc-worldsum__details", { open: true },
      h("summary", {}, "Every detail"),
      h("div.nc-worldsum__detail-grid", {},
        h("div", {}, h("span.nc-label", { id: "nc-flag-field-label" }, "Field"), swatches),
        h("div", {}, h("label.nc-label", { for: "nc-flag-charge" }, "Charge"), charge),
        h("div", {}, h("label.nc-label", { for: "nc-flag-motto" }, "Motto"), motto),
        h("div", {}, h("label.nc-label", { for: "nc-flag-line" }, "Line"), lineSelect),
        h("div", {}, h("label.nc-label", { for: "nc-flag-ribbon" }, "Ribbon"), ribbonSelect),
        h("div", {}, h("label.nc-label", { for: "nc-flag-fly" }, "Fly"), flySelect),
        h("div", {}, h("label.nc-label", { for: "nc-flag-place" }, "Place"), place),
      ),
    ),
    h("div", {}, h("label.nc-label", { for: "nc-flag-order" }, "Or tell the Steward"), order),
    h("div.nc-worldsum__actions", {}, tellBtn),
    h("p.nc-eyebrow", {}, "Steward"),
    steward,
    h("div.nc-worldsum__actions", {}, listBtn, pullBtn),
  );

  const dealHost = h("div.nc-worldsum__deal");
  const aside = h("aside.nc-worldsum__aside", {},
    workshop,
    h("h2.nc-h3", {}, "Bored nearby"),
    peopleList,
    boredEmpty,
    boredActions,
    detail,
    dealHost,
    h("h2.nc-h3", {}, "Marks"),
    h("div.nc-worldsum__key", {},
      keyItem("you", "You", true),
      keyItem("person", "Bored", true),
      keyItem("person", "Busy", false),
      keyItem("human", "Human flag", false),
      keyItem("steward", "Steward flag", false),
      keyItem("business", "Business flag", false),
    ),
  );

  // Listed flags from the house join the sample sheet. Each stands a little
  // off its place so several flags at one place stay clickable.
  async function loadLiveFlags() {
    let live;
    try {
      const response = await fetch("/api/flags/sheet");
      if (!response.ok) return;
      live = await response.json();
    } catch {
      return;
    }
    const crowd = new Map();
    for (const pin of live.pins || []) {
      const place = placeById(pin.place_id);
      if (!place || roster.some((person) => person.id === pin.id)) continue;
      const n = crowd.get(place.id) || 0;
      crowd.set(place.id, n + 1);
      const angle = (n * 2.4) + 0.8;
      roster.push({
        id: pin.id,
        flagId: pin.id,
        kind: pin.kind === "business_node" ? "business" : (pin.holder === "steward" ? "steward" : "human"),
        name: pin.name,
        label: pin.name,
        listed: true,
        bored: false,
        placeId: place.id,
        appearance: pin.appearance,
        intents: pin.intents || [],
        goodAt: pin.good_at || "",
        enjoy: pin.enjoy || "",
        refuse: pin.refuse || "",
        note: "",
        x: Math.round(place.x + Math.cos(angle) * (26 + 8 * n)),
        y: Math.round(place.y + Math.sin(angle) * (26 + 8 * n)),
      });
    }
    paintPins();
    paintBored();
  }

  paintPreview();
  paintPins();
  paintBored();
  renderDetail();
  renderDeal();
  loadLiveFlags();

  return h("section.nc-worldsum", { "aria-label": "WorldSum map" },
    h("div.nc-worldsum__body", {}, sheet, aside),
    h("ul.nc-sr-only", {}, PLACES.map((item) => h("li", {}, item.name))),
    chatHost,
  );
}
