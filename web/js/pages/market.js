import { h } from "../core/dom.js";
import "../core/theme.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";
import { worldsumMap } from "../../components/worldsum/worldsum.js";

export function marketPage() {
  const root = h("main.nc-container.nc-page", { id: "main", tabindex: "-1" });
  const hero = h("header.nc-stack", { style: { "--nc-stack-gap": "var(--nc-space-3)" } },
    h("h1.nc-h1", { id: "worldsum-title" }, "WorldSum"),
    h("p.nc-lede", {}, "A Nuuksio forest sheet, pinned to Courthouse Square and Railroad Square, then spun twice. A flag is on the sheet only when it is listed. One line to the Steward is enough, or open every detail. An intent is a mark, and it always comes with one sentence. If you are bored, invite the bored people near you into one room."),
  );
  root.append(hero, worldsumMap());
  return root;
}

const app = document.getElementById("app");
if (app) {
  app.replaceChildren(siteHeader(), marketPage(), siteFooter());
}
