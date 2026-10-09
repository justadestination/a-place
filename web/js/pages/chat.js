import { h } from "../core/dom.js";
import "../core/theme.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";
import { embed } from "../../components/chat/chat.js";

async function boot() {
  const app = document.getElementById("app") || document.getElementById("nc-chat-root");
  if (app) {
    const chatEl = await embed(new URLSearchParams(location.search));
    const main = h("main.nc-container.nc-page", { id: "main", tabindex: "-1" }, chatEl);
    app.replaceChildren(siteHeader(), main, siteFooter());
  }
}

boot();
