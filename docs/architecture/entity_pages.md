# Entity pages

**Status:** Task 2.13
**Specification:** `nightcal-master-todo.md` Section 2.13

## Pages

Every non-venue type the product renders has a page: promoter, band, comedian, and other. Venue pages stay on `/venue/`. Schema `ENTITY_TYPES` remains venue, promoter, band, and comedian. `other` is a page type and is not added to that closed set.

- Page: `/entity/?id=<id>&type=<type>`
- Embed: `/embed/entity-page/?id=<id>&type=<type>`
- Component: `web/components/entity-page/`
- Adapter: `web/js/data/entities.js`
- Link rules: `shadenet/nightcal/entity_links.py`

Each page shows the profile, contact, linked events, and linked zine articles.

## Both directions

An event matches an entity when `entityIds` contains the id, or a performer id matches, or a performer name equals the entity name. The entity page lists those events, and each event row links to the other entities on the bill. Venue event lineups link a known performer name to `/entity/?id=&type=`.

A zine article matches when it lists the entity id, or its title or body contains the entity name. The reader turns that name into a link to the entity page.

`shadenet/nightcal/entity_pages.py` is the older static generator and is left as it is.
