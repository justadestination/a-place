# Venue quick-edit and news blurbs

**Status:** Task 2.14
**Specification:** `nightcal-master-todo.md` Section 2.14

## Who can edit

The first signed-in person to claim a venue owns it. A later account cannot change that venue. An operator whose username is listed in `NIGHTCAL_OPERATORS` can edit any venue.

Writes go to `POST /api/venues/edit`. That path is behind the 21+ ZKP gate: a missing or invalid `X-ZKP-Token` is rejected before the handler runs. A missing session is 401. A session that does not own the venue is 403.

## What the form does

One page, plain labels:

- Venue name and address
- Add a show (title, date, start time)
- Publish news (title and text)

The overlay is stored in `VENUE_EDITS_PATH` (default `shadenet/data/venue_edits.json`). `GET /api/venues/edit?id=` is public so the venue page can read it.

## Immediate news

Publishing a blurb returns the saved list and the edit page renders it without a reload. The venue page embed fetches the same overlay and shows the new blurb on the next load of `/venue/?id=` or `/embed/venue-page/?id=`.
