import { h } from "../../js/core/dom.js";
import { hubZine } from "../hub-zine/hub-zine.js";
import { hubSummary } from "../hub-summary/hub-summary.js";
import { hubInbox } from "../hub-inbox/hub-inbox.js";
import { hubMarket } from "../hub-market/hub-market.js";

/**
 * Task 2.8: Hub module composition
 * Index assembled from modules:
 *   1. Today timeline (hero)
 *   2. Zine article slot
 *   3. Syndicated summary slot
 *   4. Inbox snapshot slot
 *   5. Market slot
 *
 * Rule: Slots 2–5 designed now, content later — never out-shout the hero.
 * Empty slots degrade gracefully.
 */
export function hubLayout({
  heroNode = null,
  zine = null,
  summary = null,
  inbox = null,
  market = null,
  slotHeadingLevel = 2,
} = {}) {
  const heroWrapper = h("div.nc-hub-hero", {}, heroNode || h("p.nc-muted", {}, "No timeline available today."));

  const auxiliaryGrid = h("div.nc-hub-auxiliary", { "aria-label": "Community slots" },
    hubZine(zine, { level: slotHeadingLevel }),
    hubSummary(summary, { level: slotHeadingLevel }),
    hubInbox(inbox, { level: slotHeadingLevel }),
    hubMarket(market, { level: slotHeadingLevel })
  );

  return h("div.nc-hub-layout", {}, heroWrapper, auxiliaryGrid);
}

export const meta = {
  name: "hub-layout",
  title: "Hub layout",
  summary: "Composite hub layout assembling hero today timeline and 4 auxiliary slots (zine, summary, inbox, market).",
  params: {},
};

export async function embed(params, ctx) {
  return hubLayout();
}
