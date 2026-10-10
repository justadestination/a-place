import { h } from "../../js/core/dom.js";
import { openStewardDrawer } from "../steward-drawer/steward-drawer.js";

const stewardIcon = () => {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true"); s.setAttribute("fill", "none");
  s.setAttribute("stroke", "currentColor"); s.setAttribute("stroke-width", "2"); s.setAttribute("stroke-linecap", "round");
  s.setAttribute("style", "width: 14px; height: 14px; vertical-align: middle; margin-inline-end: 5px; display: inline-block;");
  s.innerHTML = '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>';
  return s;
};

/**
 * Slot 4: Steward Inbox slot.
 * User request: "Steward Inbox and Boxes and Thoughts should switch spots."
 * Eyebrow: Steward Inbox
 * Title: Boxes & Thoughts (clickable link to open Steward drawer)
 */
export function hubInbox(inbox = null, { level = 2 } = {}) {
  const container = h("section.nc-hub-slot.nc-hub-inbox", { "aria-label": "Dispatch inbox" });

  const eyebrow = h("p.nc-eyebrow", {},
    stewardIcon(),
    "Steward Inbox"
  );

  const titleLink = h("a", {
    href: "#steward",
    style: "color: inherit; text-decoration: none; cursor: pointer;",
    onclick: (e) => {
      e.preventDefault();
      openStewardDrawer();
    }
  }, "Boxes & Thoughts");

  const count = inbox?.items?.length || 0;
  const bodyText = inbox?.summary || (count > 0 ? `${count} active thought${count === 1 ? "" : "s"} waiting for review.` : "No unread dispatches. Connect your steward to review thoughts.");

  container.append(
    h("header.nc-hub-slot__header", {},
      eyebrow,
      h(`h${level}.nc-hub-slot__title`, {}, titleLink),
    ),
    h("p.nc-hub-slot__body", {}, bodyText)
  );

  if (inbox?.items?.length) {
    const list = h("ul.nc-hub-inbox__list", {},
      ...inbox.items.slice(0, 2).map(it => h("li.nc-hub-inbox__item", {},
        h("span.nc-hub-inbox__from", {}, it.from || "Steward: "),
        h("span.nc-hub-inbox__text", {}, it.text || it.subject || "")
      ))
    );
    container.append(list);
  }

  return container;
}

export const meta = {
  name: "hub-inbox",
  title: "Hub inbox slot",
  summary: "Inbox snapshot slot: Steward Inbox eyebrow, Boxes & Thoughts title.",
  params: { count: "number of items to mock (default 0)" },
};

export async function embed(params) {
  const count = parseInt(params.get("count") || "0", 10);
  if (count <= 0) {
    return hubInbox(null);
  }
  const items = Array.from({ length: count }, (_, i) => ({
    from: `Operator ${i + 1}`,
    text: `Notice #${i + 1}: Check in on tonight's lineup.`,
  }));
  return hubInbox({ items, summary: "2 unread operator dispatches" });
}
