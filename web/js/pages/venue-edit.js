import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";
import { embed } from "../../components/venue-edit/venue-edit.js";

const root = document.getElementById("nc-edit-root");
if (root) {
  document.body.prepend(siteHeader());
  root.replaceChildren(embed(new URLSearchParams(location.search)));
  document.body.append(siteFooter());
}
