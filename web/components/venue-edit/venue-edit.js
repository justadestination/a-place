/**
 * Venue quick-edit for an owner or operator (Task 2.14).
 * Update the listing, add a show, and publish a news blurb.
 */

import { h, clear } from "../../js/core/dom.js";
import { button } from "../button/button.js";

function field(id, label, kind = "text") {
  const input = kind === "textarea"
    ? h("textarea.nc-venue-edit__textarea", { id, rows: "3" })
    : h("input.nc-venue-edit__input", { id, type: kind });
  return {
    input,
    wrap: h("label.nc-venue-edit__label", { for: id }, label, input),
  };
}

export function venueEditView({ venueId, sessionToken = "", zkpToken = "", apiBase = "" } = {}) {
  const status = h("p.nc-venue-edit__status", { id: "nc-edit-status", role: "status" }, "Sign in to edit this venue.");
  const published = h("div.nc-venue-edit__published", { id: "nc-edit-published" });
  const name = field("nc-edit-name", "Venue name");
  const address = field("nc-edit-address", "Address");
  const showTitle = field("nc-edit-show-title", "Show title");
  const date = field("nc-edit-date", "Date", "date");
  const start = field("nc-edit-start", "Start time", "time");
  const newsTitle = field("nc-edit-news-title", "News title");
  const newsText = field("nc-edit-news-text", "News text", "textarea");

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${sessionToken}`,
    "X-Session-Token": sessionToken,
    "X-ZKP-Token": zkpToken,
  };

  async function post(op, extra) {
    const resp = await fetch(`${apiBase}/api/venues/edit`, {
      method: "POST",
      headers,
      body: JSON.stringify({ venue_id: venueId, op, ...extra }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.error || `Save failed (${resp.status})`);
    return data;
  }

  function paintBlurbs(blurbs) {
    clear(published);
    for (const blurb of blurbs || []) {
      published.append(h("article.nc-venue-edit__blurb", {},
        h("h3", {}, blurb.title),
        h("p", {}, blurb.content),
      ));
    }
  }

  const save = button({
    label: "Save details",
    variant: "primary",
    onClick: async () => {
      try {
        await post("update", { name: name.input.value.trim(), address: address.input.value.trim() });
        status.textContent = "Venue details saved.";
      } catch (err) {
        status.textContent = err.message;
      }
    },
  });
  const addShow = button({
    label: "Add show",
    variant: "secondary",
    onClick: async () => {
      try {
        await post("event", {
          title: showTitle.input.value.trim(),
          date: date.input.value,
          start: start.input.value,
        });
        status.textContent = "Show added to the calendar.";
      } catch (err) {
        status.textContent = err.message;
      }
    },
  });
  const publish = button({
    label: "Publish news",
    variant: "primary",
    onClick: async () => {
      try {
        const saved = await post("blurb", {
          title: newsTitle.input.value.trim(),
          content: newsText.input.value.trim(),
        });
        paintBlurbs(saved.blurbs);
        status.textContent = "News is on the venue page.";
      } catch (err) {
        status.textContent = err.message;
      }
    },
  });

  const root = h("section.nc-venue-edit", { "aria-labelledby": "nc-edit-title" },
    h("h1.nc-venue-edit__title", { id: "nc-edit-title" }, "Edit this venue"),
    h("p.nc-venue-edit__note", {}, "Update the listing, add a show, or post news. News shows on the venue page right away."),
    status,
    h("fieldset.nc-venue-edit__form", {},
      h("legend.nc-venue-edit__heading", {}, "Venue details"),
      name.wrap,
      address.wrap,
      save,
    ),
    h("fieldset.nc-venue-edit__form", {},
      h("legend.nc-venue-edit__heading", {}, "Add a show"),
      showTitle.wrap,
      date.wrap,
      start.wrap,
      addShow,
    ),
    h("fieldset.nc-venue-edit__form", {},
      h("legend.nc-venue-edit__heading", {}, "News"),
      newsTitle.wrap,
      newsText.wrap,
      publish,
    ),
    h("h2.nc-venue-edit__heading", {}, "Published news"),
    published,
  );

  if (sessionToken && venueId) {
    post("claim").then(saved => {
      if (saved.name) name.input.value = saved.name;
      if (saved.address) address.input.value = saved.address;
      paintBlurbs(saved.blurbs);
      status.textContent = "You can edit this venue.";
    }).catch(err => {
      status.textContent = err.message;
    });
  }

  return root;
}

export const meta = {
  name: "venue-edit",
  title: "Edit a venue",
  summary: "Venue owners and operators update details, add a show, and publish news.",
  params: { id: "venue id", session: "session token", zkp: "age-verification token" },
};

export function embed(params) {
  return venueEditView({
    venueId: params?.get?.("id") || "ven_quick_edit",
    sessionToken: params?.get?.("session") || "",
    zkpToken: params?.get?.("zkp") || "",
  });
}
