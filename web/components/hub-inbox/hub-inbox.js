import { h } from "../../js/core/dom.js";

/**
 * Slot 4: Inbox snapshot slot (Steward Boxes & Thoughts).
 * Never out-shouts the hero.
 */
export function hubInbox(inbox = null, { level = 2 } = {}) {
  const container = h("section.nc-hub-slot.nc-hub-inbox", { "aria-label": "Dispatch inbox" });
  
  if (!inbox || !inbox.items || inbox.items.length === 0) {
    container.append(
      h("header.nc-hub-slot__header", {},
        h("p.nc-eyebrow", {}, "Boxes & Thoughts"),
        h(`h${level}.nc-hub-slot__title`, {}, "Steward Inbox"),
      ),
      h("p.nc-hub-slot__empty", {}, "No unread dispatches. Connect steward to review thoughts.")
    );
    return container;
  }

  const items = inbox.items.map(it => h("li.nc-hub-inbox__item", {},
    h("span.nc-hub-inbox__from", {}, it.from || "System"),
    h("span.nc-hub-inbox__text", {}, it.text || it.subject || "")
  ));

  container.append(
    h("header.nc-hub-slot__header", {},
      h("p.nc-eyebrow", {}, "Boxes & Thoughts"),
      h(`h${level}.nc-hub-slot__title`, {}, `Steward Inbox (${inbox.items.length})`),
    ),
    h("ul.nc-hub-inbox__list", {}, items)
  );
  return container;
}

export const meta = {
  name: "hub-inbox",
  title: "Hub inbox slot",
  summary: "Inbox snapshot slot for the hub index. Independently frameable.",
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
  return hubInbox({ items });
}
