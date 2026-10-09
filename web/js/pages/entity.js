import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";
import { entityPageView, embed } from "../../components/entity-page/entity-page.js";

const root = document.getElementById("nc-entity-root");
if (root) {
  document.body.prepend(siteHeader());
  root.replaceChildren(embed(new URLSearchParams(location.search)));
  document.body.append(siteFooter());
}

export { entityPageView };
