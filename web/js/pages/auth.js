import { h, params } from "../core/dom.js";
import "../core/theme.js";
import { siteHeader } from "../../components/site-header/site-header.js";
import { siteFooter } from "../../components/site-footer/site-footer.js";
import { authDialogView } from "../../components/auth-dialog/auth-dialog.js";

const app = document.getElementById("app");
const q = params();
const initialTab = q.get("tab") === "fallback" ? "fallback" : "passkey";

const view = authDialogView({
  level: 1,
  initialTab,
});

const main = h("main.nc-container.nc-page", { id: "main", tabindex: "-1" }, view);

app.replaceChildren(siteHeader(), main, siteFooter());
