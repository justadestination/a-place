"""The night calendar reads cited listings. No network."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nightcal.agent_events import EventWriteError, create_event, list_events, remove_event, update_event
from nightcal.closures import is_closed, note_for
from nightcal.fill import DAO_SOURCE, ingest_shows, record_osm_contact
from nightcal.parse_dao import acts_from_title, parse_cards, parse_time_range
from nightcal.social import probe_social, read_public_page, social_url
from nightcal.surface import apply_action, contact_for, default_ui, load_rows, messages_for, project, visible
from nightcal.votes import record_vote, vote_map
from towncrier.entities import KIND_EMAIL, KIND_PHONE, KIND_SOCIAL, add_item, ensure_entity
from towncrier.resolve import Resolver
from towncrier.store import Store

PASS = 0
FAIL = 0


def check(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}\n       got:  {got!r}\n       want: {want!r}")


CARD = """
<a class="evcard" href="/do/ross-street-sessions-michael-capella-band">
<div class="evcard-content">
<div class="evcard-content-subhead text-condensed">Food &amp; Beverage &bull; Concerts &amp; Live Music &bull; Main Street Tavern</div>
<div class="evcard-content-headline">Main Street Sessions: Funky Milagro opens for Michael Capella Band</div>
<div class="evcard-content-time"><span><i class="far fa-clock"></i></span> 6pm - 9:30pm</div>
</div>
<div class="evcard-date-box"><div class="evcard-date-dow">Fri</div><div class="evcard-date-day">2</div><div class="evcard-date-month">Oct</div></div>
</a>
<a class="evcard" href="/do/hal-sparks">
<div class="evcard-content">
<div class="evcard-content-subhead text-condensed">Comedy</div>
<div class="evcard-content-headline">Alex Mercer! Friday Night Comedy in Downtown Metropolis</div>
<div class="evcard-content-time"><span></span> 8pm - 10pm</div>
<div class="evcard-content-venue"><span></span>The Neon Foundry</div>
</div>
<div class="evcard-date-box"><div class="evcard-date-dow">Fri</div><div class="evcard-date-day">2</div><div class="evcard-date-month">Oct</div></div>
</a>
<a class="evcard" href="/do/tribe">
<div class="evcard-content">
<div class="evcard-content-headline">1TRIBE: Reggae with Konnex</div>
<div class="evcard-content-time"><span></span> 9pm - 1:30am</div>
<div class="evcard-content-venue"><span></span>The Neon Foundry</div>
</div>
<div class="evcard-date-box"><div class="evcard-date-range">Oct <span>3</span></div><div class="evcard-date-through">&mdash; To &mdash;</div><div class="evcard-date-range">Oct <span>4</span></div></div>
</a>
<a class="evcard" href="/do/trucks">
<div class="evcard-content">
<div class="evcard-content-subhead text-condensed">Main Street Tavern</div>
<div class="evcard-content-headline">Main Street Tavern Weekday Food Trucks</div>
<div class="evcard-content-time"><span></span> 11am - 2pm</div>
</div>
<div class="evcard-date-box"><div class="evcard-date-dow">Fri</div><div class="evcard-date-day">2</div><div class="evcard-date-month">Oct</div></div>
</a>
"""


def test_parse():
    cards = parse_cards(CARD, today=date(2026, 10, 2))
    check("four cards", len(cards), 4)
    sessions, sparks, tribe, trucks = cards
    check("sessions is music", sessions["kind"], "music")
    check("sessions venue falls back to Main Street Tavern", sessions["venue"], "Main Street Tavern")
    check("sessions date", sessions["start_date"], date(2026, 10, 2))
    check("sessions clock", sessions["start_clock"], (18, 0))
    check("sparks is comedy", sparks["kind"], "comedy")
    check("sparks venue", sparks["venue"], "The Neon Foundry")
    check("tribe crosses midnight onto the next morning", tribe["end_date"], date(2026, 10, 4))
    check("tribe end clock", tribe["end_clock"], (1, 30))
    check("trucks are not a show", trucks["kind"], "trucks")
    check("ampersand survived", "Food & Beverage" in sessions["categories"], True)
    check("clock range", parse_time_range("6pm - 9:30pm"), ((18, 0), (21, 30)))


def test_acts():
    check(
        "opens for names the opener first",
        acts_from_title(
            "Main Street Sessions: Funky Milagro opens for Michael Capella Band",
            "Main Street Tavern",
        ),
        [("Funky Milagro", "support"), ("Michael Capella Band", "headline")],
    )
    check(
        "comedy title keeps the name before the exclamation",
        acts_from_title("Alex Mercer! Friday Night Comedy in Downtown Metropolis", "The Neon Foundry"),
        [("Alex Mercer", "headline")],
    )
    check(
        "a food-truck listing is not a band",
        acts_from_title("Main Street Tavern Weekday Food Trucks", "Main Street Tavern"),
        [],
    )


def test_surface_from_store():
    tmp = Path(tempfile.mkdtemp(prefix="nightcal-"))
    store = Store(tmp / "t.db")
    store.upsert_source(DAO_SOURCE, "html", "https://www.downtownsantarosa.org/events/calendar")
    city = ensure_entity(store, name="Metropolis", kind="city")
    summary = ingest_shows(store, city, CARD, today=date(2026, 10, 2))
    check("four listings stored", summary["cards"], 4)
    check("resolver kept the shows apart", summary["events"], 4)

    ui = default_ui(date(2026, 10, 2))
    messages = messages_for(store, ui)
    check(
        "three A2UI messages",
        [[k for k in message if k != "version"][0] for message in messages],
        ["createSurface", "updateComponents", "updateDataModel"],
    )
    check("catalog id", messages[0]["createSurface"]["catalogId"].endswith("/nightcal/v1/catalog.json"), True)
    ids = [c["id"] for c in messages[1]["updateComponents"]["components"]]
    check("root is present", "root" in ids, True)
    check("calendar component is present", "cal" in ids, True)
    check("the ticket is gone", "ticket" in ids, False)
    cal = next(c for c in messages[1]["updateComponents"]["components"] if c["id"] == "cal")
    check("calendar reads the host view", cal["view"], {"path": "/ui/view"})
    model = messages[2]["updateDataModel"]["value"]
    check("bars share one scale", "strongest night" in model["ui"]["depthNote"], True)
    check("the sheet is tipped", "tips" in model["ui"]["depthNote"], True)
    check("house view", model["ui"]["view"], {
        "tilt": 22, "depth": 16, "bars": True, "focus": 1.2, "suspended": True,
    })
    titles = [event["title"] for event in model["ui"]["bill"]]
    check("friday night bill is the two shows, not the trucks", titles, [
        "Main Street Sessions: Funky Milagro opens for Michael Capella Band",
        "Alex Mercer! Friday Night Comedy in Downtown Metropolis",
    ])
    billings = [p["billing"] for p in model["ui"]["bill"][0]["performers"]]
    check("opener is support", "support" in billings and "headline" in billings, True)

    ui = apply_action(ui, "setScope", {"scope": "all"})
    shown = visible(model["events"], ui)
    check("all listings include the trucks", any(e["kind"] == "trucks" for e in shown), True)
    ui = apply_action(ui, "filterVenue", {"venueId": model["ui"]["bill"][1]["venueId"]})
    sparks_only = [e["title"] for e in visible(model["events"], ui)]
    check("venue filter keeps the lounge", all("Alex Mercer" in t or "1TRIBE" in t for t in sparks_only), True)
    check("venue filter drops Main Street Tavern", any("Funky" in t for t in sparks_only), False)
    ingest_shows(store, city, CARD, today=date(2026, 10, 2))
    still_up = store.one("SELECT COUNT(*) AS n FROM events WHERE active = 1")["n"]
    check("reading the calendar again does not take the shows down", still_up, 4)
    store.close()


UNPLACED = """
<a class="evcard" href="/do/halloween-bar-crawl">
<div class="evcard-content">
<div class="evcard-content-subhead text-condensed">Nightlife</div>
<div class="evcard-content-headline">The Halloween Bar Crawl - Metropolis</div>
<div class="evcard-content-time"><span></span> 4pm - 8pm</div>
</div>
<div class="evcard-date-box"><div class="evcard-date-dow">Sat</div><div class="evcard-date-day">31</div><div class="evcard-date-month">Oct</div></div>
</a>
"""


def test_missing_venue_is_not_a_room():
    tmp = Path(tempfile.mkdtemp(prefix="nightcal-venue-"))
    store = Store(tmp / "t.db")
    store.upsert_source(DAO_SOURCE, "html", "https://www.downtownsantarosa.org/events/calendar")
    city = ensure_entity(store, name="Metropolis", kind="city")
    ingest_shows(store, city, UNPLACED, today=date(2026, 10, 2))
    names = [row["name"] for row in store.query("SELECT name FROM venues")]
    check("a card with no room does not invent Downtown Metropolis", "Downtown Metropolis" in names, False)
    listing = store.one("SELECT venue_id, venue_name_raw, title_raw FROM listings")
    check("the listing is still stored", listing["title_raw"], "The Halloween Bar Crawl - Metropolis")
    check("the listing has no venue id", listing["venue_id"], None)
    event = store.one("SELECT title, venue_id, active FROM events WHERE active = 1")
    check("the show is still on the calendar", event["title"], "The Halloween Bar Crawl - Metropolis")
    check("the show is not filed under a room", event["venue_id"], None)
    store.close()


def test_closed_rooms_leave_the_rail():
    check("stout is a cited closure", is_closed("The Rusty Shamrock"), True)
    check("an open room is not closed", is_closed("The Neon Foundry"), False)
    tmp = Path(tempfile.mkdtemp(prefix="nightcal-closed-"))
    store = Store(tmp / "t.db")
    store.ensure_venue("The Rusty Shamrock", city="Metropolis", state="CA")
    store.ensure_venue("The Iron Anchor", city="Metropolis", state="CA")
    store.ensure_venue("The Neon Foundry", city="Metropolis", state="CA")
    venues, _events, hidden = load_rows(store)
    names = [row["name"] for row in venues]
    check("stout leaves the rail", "The Rusty Shamrock" in names, False)
    check("the dirty leaves the rail", "The Iron Anchor" in names, False)
    check("an open room stays", "The Neon Foundry" in names, True)
    check(
        "the note names the rooms that were actually here",
        note_for(hidden),
        "The Rusty Shamrock and the Iron Anchor are off the rail. A public notice says each one closed.",
    )
    store.close()


def test_votes_move_the_score():
    tmp = Path(tempfile.mkdtemp(prefix="nightcal-vote-"))
    store = Store(tmp / "t.db")
    store.upsert_source(DAO_SOURCE, "html", "https://www.downtownsantarosa.org/events/calendar")
    city = ensure_entity(store, name="Metropolis", kind="city")
    ingest_shows(store, city, CARD, today=date(2026, 10, 2))
    _venues, events, _hidden = load_rows(store)
    sparks = next(event for event in events if "Alex Mercer" in event["title"])
    check("a new show starts flat", sparks["score"], 0)
    record_vote(store, sparks["id"], "up")
    record_vote(store, sparks["id"], "up")
    record_vote(store, sparks["id"], "down")
    _venues, events, _hidden = load_rows(store)
    sparks = next(event for event in events if "Alex Mercer" in event["title"])
    check("two up and one down", (sparks["up"], sparks["down"], sparks["score"]), (2, 1, 1))
    other = next(event for event in events if "Funky" in event["title"])
    check("a vote stays on its own show", other["score"], 0)
    store.close()


def test_view_preferences_are_clamped():
    ui = default_ui(date(2026, 10, 3))
    hosted = dict(ui)
    hosted["view"] = {"tilt": 90, "depth": -10, "bars": False, "focus": 4}
    clamped = project([], [], hosted)["ui"]["view"]
    check("tilt cannot explode the sheet", clamped["tilt"], 24)
    check("depth cannot sink the sheet", clamped["depth"], 0)
    check("depth cannot jump the next day", project([], [], {**ui, "view": {"depth": 80}})["ui"]["view"]["depth"], 24)
    check("host can turn bars off", clamped["bars"], False)
    check("host can put the paper back", project([], [], {**ui, "view": {"suspended": False}})["ui"]["view"]["suspended"], False)
    check("focus stays in range", clamped["focus"], 1.6)
    flat = dict(ui)
    flat["view"] = {"tilt": 0, "depth": 0, "bars": False}
    check("flat sheet drops the tip", project([], [], flat)["ui"]["depthNote"], "The sheet lies flat.")
    hosted["view"] = {"tilt": 12}
    partial = project([], [], hosted)["ui"]["view"]
    check("missing depth stays the house depth", partial["depth"], 16)
    check("a set tilt is kept", partial["tilt"], 12)
    nxt = apply_action(hosted, "shiftMonth", {"delta": 1})
    check("the host tilt survives the month change", project([], [], nxt)["ui"]["view"]["tilt"], 12)
    check("a nonsense view falls back to the house", project([], [], {**ui, "view": "loud"})["ui"]["view"]["tilt"], 22)


def test_messages_are_jsonl():
    tmp = Path(tempfile.mkdtemp(prefix="nightcal-json-"))
    store = Store(tmp / "t.db")
    store.upsert_source(DAO_SOURCE, "html", "https://example.test")
    city = ensure_entity(store, name="Metropolis", kind="city")
    ingest_shows(store, city, CARD, today=date(2026, 10, 2))
    from nightcal.surface import dumps
    text = dumps(messages_for(store, default_ui(date(2026, 10, 2))))
    rows = [json.loads(line) for line in text.splitlines() if line]
    check("jsonl round trip", len(rows), 3)
    check("data model path is the root", rows[2]["updateDataModel"]["path"], "/")
    store.close()


PUBLIC_EVENT = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
  {"@type":"MusicEvent","name":"Public Room Night","startDate":"2026-10-17T21:00:00-07:00",
   "url":"https://www.instagram.com/p/publicroomnight"}
]}
</script>
</head><body><p>Public Room Night</p></body></html>
"""

UNDATED = """
<script type="application/ld+json">
{"@type":"Event","name":"No Date Night"}
</script>
"""

LOGIN_WITH_EVENT = """
<html><title>Facebook</title>
<script type="application/ld+json">
{"@type":"MusicEvent","name":"Should Not Import","startDate":"2026-10-17T21:00:00-07:00"}
</script>
<p>Log in to Facebook</p>
</html>
"""


def test_arlene_francis_center_is_in_the_gazetteer_query():
    from nightcal.fill import DOWNTOWN_BBOX, _downtown_query
    query = _downtown_query(DOWNTOWN_BBOX)
    check(
        "the named building is requested inside downtown",
        'nwr["name"="The Commons Arts Center"]["building"]' in query,
        True,
    )
    check(
        "that statement still carries the downtown box",
        query.count("(38.42800,-122.73600,38.45400,-122.69800)"),
        5,
    )


def test_osm_contact_is_cited_not_invented():
    check("a bare handle is that profile", social_url("instagram", "russianriverbrewingofficial"),
          "https://www.instagram.com/russianriverbrewingofficial")
    check("an x handle lands on x", social_url("twitter", "@rrbc"), "https://x.com/rrbc")
    check("http on the same host is linked as https", social_url("facebook", "http://facebook.com/rr"),
          "https://facebook.com/rr")
    check("a share button is not a profile", social_url("facebook", "https://www.facebook.com/sharer/sharer.php?u=1"), None)
    check("a sentence is not a handle", social_url("facebook", "not a handle"), None)
    tmp = Path(tempfile.mkdtemp(prefix="nightcal-contact-"))
    store = Store(tmp / "t.db")
    city = ensure_entity(store, name="Metropolis", kind="city")
    entity = ensure_entity(store, name="Metropolis Brewing Company", kind="venue", parent_id=city, role="host")
    store.ensure_venue("Metropolis Brewing Company", city="Metropolis", state="CA")
    osm = "https://www.openstreetmap.org/node/1"
    add_item(
        store, entity_id=entity, kind=KIND_SOCIAL, value="osm:node/1", display="Metropolis Brewing Company",
        source_id="osm:node/1", source_url=osm, citation_kind="html",
    )
    record_osm_contact(store, entity, {
        "email": "info@russianriverbrewing.com",
        "contact:facebook": "https://www.facebook.com/russianriverbrewing",
        "contact:instagram": "russianriverbrewingofficial",
        "phone": "+1 707-545-2337",
    }, "osm:node/1", osm)
    contact = contact_for(store, entity)
    check("email is the one OSM stated", [row["text"] for row in contact["emails"]], ["info@russianriverbrewing.com"])
    check("facebook and instagram, no invented X", [row["text"] for row in contact["socials"]], ["Facebook", "Instagram"])
    venues, _events, _hidden = load_rows(store)
    shown = next(row for row in venues if row["name"] == "Metropolis Brewing Company")
    check("the rail carries the cited links", [row["text"] for row in shown["contact"]["socials"]], ["Facebook", "Instagram"])
    check("the map identity is not a profile", any(row["href"].startswith("osm:") for row in shown["contact"]["socials"]), False)
    add_item(
        store, entity_id=entity, kind=KIND_PHONE, value="(811) 564-0956", display="(811) 564-0956",
        source_id="web:example.test", source_url="https://example.test/room",
        citation_kind="html", excerpt="instagram id 18115640956824059",
    )
    add_item(
        store, entity_id=entity, kind=KIND_EMAIL, value="user@domain.com", display="user@domain.com",
        source_id="web:example.test", source_url="https://example.test/room",
        citation_kind="html", excerpt="follow the format user@domain.com",
    )
    contact = contact_for(store, entity)
    check("an id that looks like a phone stays off the rail", "(811) 564-0956" in [row["text"] for row in contact["phones"]], False)
    check("a placeholder address stays off the rail", "user@domain.com" in [row["text"] for row in contact["emails"]], False)
    store.close()


def test_social_pages_do_not_invent_shows():
    check("a public event with a date is kept", read_public_page(PUBLIC_EVENT, "https://www.instagram.com/barrelproof", 200)["kind"], "events")
    check("an event with no date is not given one", read_public_page(UNDATED, "https://www.facebook.com/barrelproof", 200)["events"], [])
    walled = read_public_page(LOGIN_WITH_EVENT, "https://www.facebook.com/login", 200)
    check("a login wall drops the event that came with it", walled["kind"], "login")
    check("a login wall stores nothing", walled["events"], [])

    tmp = Path(tempfile.mkdtemp(prefix="nightcal-social-"))
    store = Store(tmp / "t.db")
    store.upsert_source(DAO_SOURCE, "html", "https://www.downtownsantarosa.org/events/calendar")
    city = ensure_entity(store, name="Metropolis", kind="city")
    ingest_shows(store, city, CARD, today=date(2026, 10, 2))
    venue = store.one("SELECT id FROM venues WHERE name = ?", ("The Neon Foundry",))
    entity = ensure_entity(store, name="The Neon Foundry", kind="venue", parent_id=city, role="host")
    for url in (
        "https://www.facebook.com/barrelproof",
        "https://www.instagram.com/barrelproof",
        "https://x.com/barrelproof",
    ):
        add_item(
            store, entity_id=entity, kind=KIND_SOCIAL, value=url, display=url,
            source_id="test", source_url="https://www.downtownsantarosa.org/events/calendar",
            citation_kind="html",
        )
    _venues, events, _hidden = load_rows(store)
    sparks = next(event for event in events if "Alex Mercer" in event["title"])
    record_vote(store, sparks["id"], "up")

    def fetch(url):
        if "facebook.com" in url:
            return {"status": 200, "url": "https://www.facebook.com/login", "html": LOGIN_WITH_EVENT, "error": ""}
        if "instagram.com" in url:
            return {"status": 200, "url": url, "html": PUBLIC_EVENT, "error": ""}
        return {"status": 0, "url": url, "html": "", "error": "URLError"}

    summary = probe_social(store, city, fetch=fetch, today=date(2026, 10, 3))
    check("the note says facebook asked for a login", "Facebook asked for a login" in summary["note"], True)
    check("the note counts the public show", "Instagram listed 1 show" in summary["note"], True)
    check("the note says X did not answer", "X did not answer" in summary["note"], True)
    titles = [row["title_raw"] for row in store.query("SELECT title_raw FROM listings")]
    check("the walled event was not stored", "Should Not Import" in titles, False)
    check("the public event was stored", "Public Room Night" in titles, True)
    downtown = store.one(
        "SELECT missing_since FROM listings WHERE source_id = ? AND title_raw LIKE ?",
        (DAO_SOURCE, "Alex Mercer%"),
    )
    check("the downtown listing is not marked missing", downtown["missing_since"], None)
    _venues, events, _hidden = load_rows(store)
    sparks = next(event for event in events if "Alex Mercer" in event["title"])
    check("the sample vote stays on the downtown show", sparks["score"], 1)
    public = next(event for event in events if event["title"] == "Public Room Night")
    check("the public show is filed at the room that cited the page", public["venueId"], venue["id"])
    check("the public show keeps the date the page printed", public["date"], "2026-10-17")
    store.close()


def _refused(store, call):
    try:
        call()
    except EventWriteError as exc:
        return exc.message
    check("the write was refused", False, True)
    return ""


def test_agent_can_file_correct_and_remove_a_show():
    tmp = Path(tempfile.mkdtemp(prefix="nightcal-agent-"))
    store = Store(tmp / "t.db")
    store.upsert_source(DAO_SOURCE, "html", "https://www.downtownsantarosa.org/events/calendar")
    city = ensure_entity(store, name="Metropolis", kind="city")
    ingest_shows(store, city, CARD, today=date(2026, 10, 2))
    listings_before = store.one("SELECT COUNT(*) AS n FROM listings")["n"]
    sparks = next(event for event in load_rows(store)[1] if "Alex Mercer" in event["title"])
    record_vote(store, sparks["id"], "up")
    votes_before = vote_map(store)
    dao = store.one(
        "SELECT title_raw, starts_at, url FROM listings WHERE source_id = ? AND title_raw LIKE ?",
        (DAO_SOURCE, "Alex Mercer%"),
    )

    message = _refused(store, lambda: create_event(store, {
        "title": "No Citation",
        "startsAt": "2026-10-09T20:00:00-07:00",
        "kind": "music",
    }))
    check("a show needs a public page", "sourceUrl" in message, True)
    message = _refused(store, lambda: create_event(store, {
        "title": "Local",
        "startsAt": "2026-10-09T20:00:00-07:00",
        "sourceUrl": "http://localhost/show",
        "kind": "music",
    }))
    check("this machine is not a source", "public page" in message, True)
    message = _refused(store, lambda: create_event(store, {
        "title": "No Zone",
        "startsAt": "2026-10-09T20:00:00",
        "sourceUrl": "https://example.com/zone",
        "kind": "music",
    }))
    check("a bare clock is refused", "timezone" in message, True)
    message = _refused(store, lambda: create_event(store, {
        "title": "Invented Room",
        "startsAt": "2026-10-09T20:00:00-07:00",
        "sourceUrl": "https://example.com/room",
        "venue": "Not A Real Room",
        "kind": "music",
    }))
    check("an unknown room is refused", "does not add rooms" in message, True)
    check(
        "no room was invented",
        store.one("SELECT COUNT(*) AS n FROM venues WHERE name = ?", ("Not A Real Room",))["n"],
        0,
    )
    check(
        "a refused show writes no listing",
        store.one("SELECT COUNT(*) AS n FROM listings")["n"],
        listings_before,
    )

    _action, filed = create_event(store, {
        "title": "Arlene Late Set",
        "startsAt": "2026-10-09T21:00:00-07:00",
        "endsAt": "2026-10-09T23:00:00-07:00",
        "venue": "The Neon Foundry",
        "kind": "music",
        "sourceUrl": "https://example.com/arlene-late",
        "externalId": "late-1",
    })
    check("the filing is created", filed["action"], "created")
    check("it lands on the cited night", filed["event"]["date"], "2026-10-09")
    check("it lands at the room that was named", filed["event"]["venue"], "The Neon Foundry")
    check("the kind is the one that was filed", filed["event"]["kind"], "music")
    _action, again = create_event(store, {
        "title": "Arlene Late Set",
        "startsAt": "2026-10-09T21:00:00-07:00",
        "venue": "The Neon Foundry",
        "kind": "music",
        "sourceUrl": "https://example.com/arlene-late",
        "externalId": "late-1",
    })
    check("the same filing updates", again["action"], "updated")
    check("it does not become a second show", again["event"]["id"], filed["event"]["id"])
    check(
        "one agent listing",
        store.one("SELECT COUNT(*) AS n FROM listings WHERE source_id = 'agent'")["n"],
        1,
    )

    corrected = update_event(store, sparks["id"], {
        "title": "Alex Mercer! Friday Night Comedy, sold out",
        "sourceUrl": "https://example.com/hal-note",
    })
    check("the sheet shows the correction", corrected["event"]["title"], "Alex Mercer! Friday Night Comedy, sold out")
    check(
        "the downtown listing title stays",
        store.one("SELECT title_raw FROM listings WHERE url = ?", (dao["url"],))["title_raw"],
        dao["title_raw"],
    )
    check(
        "the downtown listing time stays",
        store.one("SELECT starts_at FROM listings WHERE url = ?", (dao["url"],))["starts_at"],
        dao["starts_at"],
    )
    titles = [event["title"] for event in load_rows(store)[1] if "Alex Mercer" in event["title"]]
    check("the correction does not duplicate the show", len(titles), 1)
    check("the sample vote stays on that show", next(event["score"] for event in load_rows(store)[1] if "Alex Mercer" in event["title"]), 1)
    check("downtown is still cited beside the correction", "downtown_santa_rosa" in [row["source"] for row in corrected["event"]["listings"]], True)

    moved = update_event(store, corrected["event"]["id"], {
        "startsAt": "2026-10-16T20:00:00-07:00",
        "sourceUrl": "https://example.com/hal-moved",
    })
    check("the moved show is on the new night", moved["event"]["date"], "2026-10-16")
    still = [
        event["date"] for event in load_rows(store)[1]
        if "Alex Mercer" in event["title"]
    ]
    check("the old night is not left up beside it", still, ["2026-10-16"])
    check(
        "the downtown card still says the original time",
        store.one("SELECT starts_at FROM listings WHERE url = ?", (dao["url"],))["starts_at"],
        dao["starts_at"],
    )

    renamed = update_event(store, filed["event"]["id"], {
        "title": "Arlene Late Set, second billing",
        "sourceUrl": "https://example.com/arlene-late",
    })
    check("a new title resolves to a new id", renamed["event"]["id"] != filed["event"]["id"], True)
    removed = remove_event(store, filed["event"]["id"], {"sourceUrl": "https://example.com/arlene-late"})
    check("the original id still removes that show", removed["event"]["id"], renamed["event"]["id"])
    check("removal is marked, not deleted", removed["event"]["suppressed"], True)
    check(
        "the removed show leaves the sheet",
        any("Arlene Late Set" in event["title"] for event in load_rows(store)[1]),
        False,
    )
    check(
        "the listing row is still in the database",
        store.one("SELECT COUNT(*) AS n FROM listings WHERE external_id = 'late-1'")["n"],
        1,
    )
    Resolver(store).resolve()
    check(
        "a resolve does not put the removed show back",
        any("Arlene Late Set" in event["title"] for event in load_rows(store)[1]),
        False,
    )
    restored = update_event(store, filed["event"]["id"], {"suppressed": False})
    check("clearing the removal brings it back", restored["action"], "restored")
    check(
        "the restored show is on the sheet",
        any(event["title"] == "Arlene Late Set, second billing" for event in load_rows(store)[1]),
        True,
    )
    message = _refused(store, lambda: remove_event(store, filed["event"]["id"], {}))
    check("removal needs a page too", "sourceUrl" in message, True)
    check(
        "a refused removal leaves the show up",
        any(event["title"] == "Arlene Late Set, second billing" for event in load_rows(store)[1]),
        True,
    )

    ingest_shows(store, city, CARD, today=date(2026, 10, 2))
    check(
        "a calendar reread keeps the filed show",
        any(event["title"] == "Arlene Late Set, second billing" for event in load_rows(store)[1]),
        True,
    )
    remove_event(store, moved["event"]["id"], {
        "sourceUrl": "https://example.com/hal-off",
        "reason": "the room posted that it moved off this date",
    })
    ingest_shows(store, city, CARD, today=date(2026, 10, 2))
    check(
        "a taken-down downtown show stays off the sheet",
        any("Alex Mercer" in event["title"] for event in load_rows(store)[1]),
        False,
    )
    check(
        "its downtown listing is still stored",
        store.one("SELECT title_raw FROM listings WHERE url = ?", (dao["url"],))["title_raw"],
        dao["title_raw"],
    )
    found = list_events(store, {"date": ["2026-10-09"]})
    check("a date query returns the filed night", [event["title"] for event in found["events"]], ["Arlene Late Set, second billing"])
    check("votes were not rewritten", vote_map(store), votes_before)
    store.close()


if __name__ == "__main__":
    test_parse()
    test_acts()
    test_surface_from_store()
    test_missing_venue_is_not_a_room()
    test_closed_rooms_leave_the_rail()
    test_votes_move_the_score()
    test_view_preferences_are_clamped()
    test_messages_are_jsonl()
    test_arlene_francis_center_is_in_the_gazetteer_query()
    test_osm_contact_is_cited_not_invented()
    test_social_pages_do_not_invent_shows()
    test_agent_can_file_correct_and_remove_a_show()
    print(f"{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)
