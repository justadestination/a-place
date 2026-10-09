/**
 * Dedicated page for a promoter, band, comedian, or other entity (Task 2.13).
 */

import { h } from "../../js/core/dom.js";
import {
  SEED_ENTITIES,
  SEED_EVENTS,
  SEED_ARTICLES,
  getEntity,
  listEntities,
  eventsForEntity,
  articlesForEntity,
  entitiesForEvent,
  entityHref,
} from "../../js/data/entities.js";

const TYPE_LABEL = {
  promoter: "Promoter",
  band: "Band",
  comedian: "Comedian",
  other: "Other",
};

function contactLinks(items) {
  const wrap = h("dd");
  if (!items || items.length === 0) {
    wrap.append("None listed");
    return wrap;
  }
  for (const item of items) {
    wrap.append(h("a.nc-entity-page__contact-link", { href: item.href }, item.text));
  }
  return wrap;
}

export function entityPageView({ entity, events = [], articles = [] } = {}) {
  const typeLabel = TYPE_LABEL[entity.type] || "Entity";
  const root = h("article.nc-entity-page", { "aria-labelledby": "nc-entity-title" });

  const profile = h("section.nc-entity-page__section", { "aria-labelledby": "nc-entity-profile" },
    h("p.nc-entity-page__eyebrow", {}, typeLabel),
    h("h1.nc-entity-page__title", { id: "nc-entity-title" }, entity.name),
    h("p.nc-entity-page__status", {}, `Status: ${entity.status || "active"}`),
    h("h2.nc-entity-page__heading", { id: "nc-entity-profile" }, "Profile"),
    h("p.nc-entity-page__bio", {}, entity.bio || "No profile written yet."),
  );

  const contact = entity.contact || {};
  const details = h("dl.nc-entity-page__grid");
  details.append(h("dt", {}, "Phone"), contactLinks(contact.phones));
  details.append(h("dt", {}, "Email"), contactLinks(contact.emails));
  details.append(h("dt", {}, "Web"), contactLinks(contact.websites));
  const contactSection = h("section.nc-entity-page__section", { "aria-labelledby": "nc-entity-contact" },
    h("h2.nc-entity-page__heading", { id: "nc-entity-contact" }, "Contact"),
    details,
  );

  const eventList = h("ul.nc-entity-page__list");
  if (events.length === 0) {
    eventList.append(h("li.nc-entity-page__empty", {}, "No linked events yet."));
  } else {
    for (const event of events) {
      const row = h("li.nc-entity-page__event");
      const titleHref = event.venueId ? `/venue/?id=${encodeURIComponent(event.venueId)}` : `/today#${encodeURIComponent(event.id)}`;
      row.append(h("a.nc-entity-link", { href: titleHref }, event.title));
      row.append(h("span.nc-entity-page__when", {}, [event.date, event.start].filter(Boolean).join(" ")));
      for (const linked of entitiesForEvent(event)) {
        row.append(h("a.nc-entity-link", { href: entityHref(linked) }, linked.name));
      }
      eventList.append(row);
    }
  }
  const eventSection = h("section.nc-entity-page__section", { "aria-labelledby": "nc-entity-events" },
    h("h2.nc-entity-page__heading", { id: "nc-entity-events" }, "Linked events"),
    eventList,
  );

  const articleList = h("ul.nc-entity-page__list");
  if (articles.length === 0) {
    articleList.append(h("li.nc-entity-page__empty", {}, "No linked zine articles yet."));
  } else {
    for (const article of articles) {
      articleList.append(h("li", {},
        h("a.nc-entity-link", { href: `/zine/?node=${encodeURIComponent(article.id)}` }, article.title),
      ));
    }
  }
  const articleSection = h("section.nc-entity-page__section", { "aria-labelledby": "nc-entity-articles" },
    h("h2.nc-entity-page__heading", { id: "nc-entity-articles" }, "Linked zine articles"),
    articleList,
  );

  root.append(profile, contactSection, eventSection, articleSection);
  return root;
}

export const meta = {
  name: "entity-page",
  title: "Entity page",
  summary: "Profile, contact, linked events, and linked zine articles for a promoter, band, comedian, or other entity.",
  params: { id: "entity id", type: "promoter | band | comedian | other" },
};

export function embed(params) {
  const requestedType = params?.get?.("type") || "";
  const requestedId = params?.get?.("id") || "";
  const entity = getEntity(requestedId)
    || listEntities(requestedType)[0]
    || SEED_ENTITIES[0];
  return entityPageView({
    entity,
    events: eventsForEntity(entity, SEED_EVENTS),
    articles: articlesForEntity(entity, SEED_ARTICLES),
  });
}
