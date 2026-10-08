-- towncrier schema
--
-- Design notes:
--
--   An *event* is not a thing we discover. It is a *cluster of listings* that
--   we infer. So the unit of storage is `listing` (one mention of an event on
--   one source), and `event` is the deduplicated aggregate we resolve those
--   listings into. Every confidence signal is derived from listings, which
--   keeps the raw evidence intact and auditable.
--
--   Confidence is deliberately NOT one number. Existence corroboration and
--   reliability are different axes:
--     * corroboration — how many independent places list it (your "1 point
--       per place found")
--     * reliability   — does this performer/venue keep its commitments
--   A well-promoted show by a flaky band is real but risky; a single
--   listing by a reliable venue is thin but solid. Keeping them separate lets
--   the ranking be explicit instead of a magic number.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;


-- ================================================================ THE TREE
--
-- The project is modelled as an oak:
--
--     Metropolis          trunk
--      ├── The Royal      branch   (venue)
--      │    ├── Foo       leaf     (band playing here)
--      │    └── Show      acorn    (an event on this branch)
--      └── promoter       leaf
--
-- `entities` holds the trunk, branches and leaves. `events` (defined below)
-- are the acorns: they hang off a branch, not off the trunk.
--
-- The trunk/branches/leaves distinction matters operationally, not
-- decoratively: it is what tells the discovery crawler where to point
-- (branches = places that host events) and what the leaves are *for* (acts
-- that play on branches, organizers that book them). A promoter is a leaf
-- hanging off every venue they book for, not an attribute of any one venue —
-- "they don't book their own shows" is a many-to-many edge, not a field.

CREATE TABLE IF NOT EXISTS entities (
    id          TEXT PRIMARY KEY,   -- stable: 'ent_<hash>'
    kind        TEXT NOT NULL,      -- city | venue | band | promoter
    name        TEXT NOT NULL,
    parent_id   TEXT REFERENCES entities(id) ON DELETE SET NULL,
    slug        TEXT,
    -- Role within the tree, for humans reading the db: 'host' | 'act' | 'booking'
    role        TEXT,
    -- Free-form extras (genres, hours, a bio).
    meta        TEXT NOT NULL DEFAULT '{}',
    -- Identity of an entity is "same thing seen twice", which is the hard
    -- problem for promoters (one person, three room names). Human-confirmed
    -- entities stop being re-merged.
    verified    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_entities_parent ON entities(parent_id);
CREATE INDEX IF NOT EXISTS idx_entities_kind   ON entities(kind);
CREATE INDEX IF NOT EXISTS idx_entities_name   ON entities(name);


-- Many-to-many edges that the parent_id column cannot express: a promoter
-- books several venues, a band plays at several. `role` says how.
CREATE TABLE IF NOT EXISTS entity_links (
    from_id   TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    to_id     TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    -- 'books' (promoter -> venue), 'plays_at' (band -> venue),
    -- 'promotes' (band/promoter -> band), 'co_books' (organizer <-> organizer)
    rel       TEXT NOT NULL,
    source_id TEXT,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (from_id, to_id, rel)
);
CREATE INDEX IF NOT EXISTS idx_links_to ON entity_links(to_id);


-- ================================================================ ITEMS
--
-- A fact about an entity: a phone number, an email, a street address, an
-- Instagram handle, a set of opening hours.
--
-- Why items are not columns on `entities`: the rule this project follows is
-- "we publish what we can support with a public source, and we never invent
-- or fill in a blank." That is only enforceable if every fact is a row that
-- carries its own provenance. A column can be NULL with no record of *why*,
-- and two sources can disagree with nowhere to put the second opinion.
--
-- Consequences of modelling it this way, which are the point:
--   * A missing phone number does not disqualify a venue. The venue is the
--     record; the phone number is one item that may or may not exist.
--   * Conflicting information is representable: two rows, same entity, same
--     kind, different values, each with its own source. Nothing is
--     overwritten and nothing is invented to reconcile them.
--   * Everything is citable, because a fact with no source is not a fact we
--     publish — it is just a column someone typed.

CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY,
    entity_id   TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,   -- phone|email|website|address|social|hours|other
    -- Normalized for comparison (lowercased, digits-only for phone).
    value       TEXT NOT NULL,
    -- Exactly as the source stated it, kept so we can show the original.
    display     TEXT,
    -- Provenance. Every published fact must have both of these.
    source_id   TEXT,
    source_url  TEXT,
    -- 0..1. How much this specific source can be trusted for this kind of
    -- fact. The venue's own site outranks an aggregator's guess.
    confidence  REAL,
    -- Set when another source states a different value for the same
    -- entity+kind. The conflict is recorded, not resolved: both stay
    -- visible, and the review queue decides which, if either, to feature.
    conflicts_with INTEGER,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(entity_id, kind, value)
);
CREATE INDEX IF NOT EXISTS idx_items_entity ON items(entity_id, kind);
CREATE INDEX IF NOT EXISTS idx_items_kind   ON items(kind);

-- Every published fact traces to a public source. This is the audit trail
-- that makes "we only use publicly available information" checkable rather
-- than a claim: a fact with no source_url is not eligible for publication.
-- One row per (item, source) — NOT one per item. Keying on item_id alone
-- would let a second source overwrite the first, destroying the provenance
-- this table exists to preserve. The composite key also makes re-asserting
-- the same fact from the same source idempotent.
CREATE TABLE IF NOT EXISTS citations (
    item_id    INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    source_id  TEXT NOT NULL,
    source_url TEXT NOT NULL,
    -- 'structured_data' (schema.org JSON-LD on the venue's own page),
    -- 'rss' (the venue's own feed), 'html' (a public page we read),
    -- 'manual' (typed in by the operator), 'derived' (inferred, never
    -- published as a standalone fact)
    kind       TEXT NOT NULL,
    retrieved_at TEXT NOT NULL DEFAULT (datetime('now')),
    -- Verbatim snippet of the source that produced the value.
    excerpt    TEXT,
    PRIMARY KEY (item_id, source_id)
);
CREATE INDEX IF NOT EXISTS idx_citations_source ON citations(source_id);


-- ---------------------------------------------------------------- sources

CREATE TABLE IF NOT EXISTS sources (
    id          TEXT PRIMARY KEY,   -- 'venue_site', 'rss:example.com', 'bandsintown'
    kind        TEXT NOT NULL,      -- jsonld | rss | api | manual
    base_url    TEXT,
    -- Polling cadence and politeness. A source that 429s us must back off,
--   not retry harder.
    interval_min INTEGER NOT NULL DEFAULT 60,
    min_delay_sec REAL    NOT NULL DEFAULT 5.0,
    enabled     INTEGER NOT NULL DEFAULT 1,
    last_polled_at TEXT,
    last_status  TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0
);


-- ---------------------------------------------------------------- venues

CREATE TABLE IF NOT EXISTS venues (
    id            TEXT PRIMARY KEY,  -- stable slug, e.g. 'the-royal'
    name          TEXT NOT NULL,
    address       TEXT,
    city          TEXT,
    state         TEXT,
    lat           REAL,
    lon           REAL,
    website       TEXT,
    -- Free-form: 'facebook_page_url', 'instagram_handle', 'email'
    handles       TEXT NOT NULL DEFAULT '{}',  -- JSON object
    -- Rolling reliability, recomputed by trust.py. 0.0..1.0
    trust_score   REAL,
    events_listed INTEGER NOT NULL DEFAULT 0,
    events_cancelled INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_venues_city ON venues(city);
CREATE INDEX IF NOT EXISTS idx_venues_geo  ON venues(lat, lon);


-- ---------------------------------------------------------------- performers

CREATE TABLE IF NOT EXISTS performers (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    -- 'band' | 'dj' | 'comic' | 'speaker' | 'unknown'
    kind          TEXT NOT NULL DEFAULT 'unknown',
    bio           TEXT,
    genres        TEXT NOT NULL DEFAULT '[]',  -- JSON array
    image_url     TEXT,
    -- External identifiers let the enrichment agent avoid re-researching
    -- an artist it has already profiled.
    external_ids  TEXT NOT NULL DEFAULT '{}',  -- {bandsintown: 1234, ...}
    trust_score   REAL,
    events_listed INTEGER NOT NULL DEFAULT 0,
    events_cancelled INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_performers_name ON performers(name);


-- ---------------------------------------------------------------- listings
--
-- One row per (source, external_id): a single mention of a single event.
-- `raw_json` keeps whatever the source actually said so we can re-derive
-- fields after a parser improvement without re-scraping history.

CREATE TABLE IF NOT EXISTS listings (
    id            INTEGER PRIMARY KEY,
    source_id     TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    external_id   TEXT NOT NULL,   -- source's own id or canonical URL
    url           TEXT,
    -- Extracted, pre-dedup fields
    title_raw     TEXT NOT NULL,
    title_norm    TEXT NOT NULL,   -- normalized for fuzzy matching
    description   TEXT,
    starts_at     TEXT,            -- ISO 8601 with offset
    ends_at       TEXT,
    all_day       INTEGER NOT NULL DEFAULT 0,
    -- 'EventScheduled' | 'EventCancelled' | 'EventPostponed' | ...
    status        TEXT NOT NULL DEFAULT 'EventScheduled',
    venue_id      TEXT REFERENCES venues(id) ON DELETE SET NULL,
    venue_name_raw TEXT,
    lat           REAL,
    lon           REAL,
    ticket_url    TEXT,
    price         TEXT,
    image_url     TEXT,
    -- Lifecycle: the first time we saw this listing, and the last.
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at  TEXT NOT NULL DEFAULT (datetime('now')),
    -- A listing we can no longer fetch may have been deleted (cancelled) or
--   just moved/rotated. We record the disappearance rather than deleting the
--   row, because the evidence of a retraction is itself a signal.
    missing_since TEXT,
    missing_count INTEGER NOT NULL DEFAULT 0,
    raw_json      TEXT,
    UNIQUE(source_id, external_id)
);
CREATE INDEX IF NOT EXISTS idx_listings_title  ON listings(title_norm);
CREATE INDEX IF NOT EXISTS idx_listings_starts ON listings(starts_at);
CREATE INDEX IF NOT EXISTS idx_listings_venue  ON listings(venue_id);
CREATE INDEX IF NOT EXISTS idx_listings_missing ON listings(missing_since);


-- ---------------------------------------------------------------- events
--
-- The resolved aggregate. A cluster of listings believed to be one real-world
-- event.

CREATE TABLE IF NOT EXISTS events (
    id            TEXT PRIMARY KEY,  -- stable hash of the cluster key
    title         TEXT NOT NULL,
    title_norm    TEXT NOT NULL,
    description   TEXT,
    starts_at     TEXT NOT NULL,     -- canonical (UTC) start
    ends_at       TEXT,
    timezone      TEXT,
    venue_id      TEXT REFERENCES venues(id) ON DELETE SET NULL,
    status        TEXT NOT NULL DEFAULT 'EventScheduled',
    ticket_url    TEXT,
    price         TEXT,
    image_url     TEXT,
    -- Corroboration: count of distinct sources that list this event.
    -- This is the user's "1 point per place we can find it listed".
    source_count  INTEGER NOT NULL DEFAULT 1,
    listing_count INTEGER NOT NULL DEFAULT 1,
    -- 0..1, derived from corroboration breadth and agreement. Never from
    --   volume alone: ten posts of the same flyer is one source of evidence.
    confidence    REAL NOT NULL DEFAULT 0.0,
    -- Whether we auto-publish to the .ics feed or hold for review.
    needs_review  INTEGER NOT NULL DEFAULT 1,
    review_reason TEXT,
    -- 1 while the event is in the past, so the feed can be trimmed.
    active        INTEGER NOT NULL DEFAULT 1,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at  TEXT NOT NULL DEFAULT (datetime('now')),
    cancelled_at  TEXT,
    -- Free-form provenance for the reviewer UI.
    notes         TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_starts  ON events(starts_at);
CREATE INDEX IF NOT EXISTS idx_events_venue   ON events(venue_id);
CREATE INDEX IF NOT EXISTS idx_events_review  ON events(needs_review);
CREATE INDEX IF NOT EXISTS idx_events_active  ON events(active, starts_at);


-- Mapping of listings to the event they resolved into. A listing belongs to
-- at most one event, but we keep the join table so re-resolution is auditable
-- and so we can explain *why* two listings were merged.
CREATE TABLE IF NOT EXISTS event_listings (
    event_id   TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    -- Similarity score that caused the merge, for auditing.
    match_score REAL,
    match_reason TEXT,
    assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (event_id, listing_id)
);
CREATE INDEX IF NOT EXISTS idx_evl_listing ON event_listings(listing_id);


CREATE TABLE IF NOT EXISTS event_performers (
    event_id      TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    performer_id  TEXT NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
    -- 'headline' | 'support' | 'host' | 'unknown'
    billing       TEXT NOT NULL DEFAULT 'unknown',
    display_name  TEXT,            -- as written in this listing
    PRIMARY KEY (event_id, performer_id)
);
CREATE INDEX IF NOT EXISTS idx_ep_performer ON event_performers(performer_id);


-- ---------------------------------------------------------------- scans
--
-- Scan history. This is what makes cancellation detection possible: we need
-- to know what a source looked like *last* time to notice a retraction.

CREATE TABLE IF NOT EXISTS scans (
    id          INTEGER PRIMARY KEY,
    source_id   TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    status      TEXT NOT NULL DEFAULT 'running',  -- running|ok|error
    -- 'ok' | 'rate_limited' | 'not_found' | 'parse_error' | 'http_error'
    error_kind  TEXT,
    http_status INTEGER,
    listings_seen   INTEGER NOT NULL DEFAULT 0,
    listings_new    INTEGER NOT NULL DEFAULT 0,
    listings_changed INTEGER NOT NULL DEFAULT 0,
    listings_gone   INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER,
    detail      TEXT
);
CREATE INDEX IF NOT EXISTS idx_scans_source ON scans(source_id, started_at DESC);


-- An event that changed status between scans (cancelled, postponed, moved).
-- Kept as a timeline so the .ics feed can emit a proper cancellation or
-- reschedule update rather than silently dropping an event.
CREATE TABLE IF NOT EXISTS event_changes (
    id          INTEGER PRIMARY KEY,
    event_id    TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    changed_at  TEXT NOT NULL DEFAULT (datetime('now')),
    field       TEXT NOT NULL,   -- status | starts_at | venue_id | title
    old_value   TEXT,
    new_value   TEXT,
    reason      TEXT,
    scan_id     INTEGER REFERENCES scans(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_changes_event ON event_changes(event_id, changed_at DESC);


-- ---------------------------------------------------------------- enrichment
--
-- The research agent's output about a performer. Separate from the
-- performers row so re-research doesn't clobber manually curated fields.

CREATE TABLE IF NOT EXISTS performer_research (
    id           INTEGER PRIMARY KEY,
    performer_id TEXT NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
    researched_at TEXT NOT NULL DEFAULT (datetime('now')),
    summary      TEXT,
    -- JSON array of {label, value, source_url, confidence}
    facts        TEXT NOT NULL DEFAULT '[]',
    -- Free text the agent used, for debugging a bad summary.
    model        TEXT,
    tokens_used  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_research_performer ON performer_research(performer_id, researched_at DESC);


-- Open questions the system could not resolve on its own. Answering one
-- closes the loop: the answer is written back to the event.
CREATE TABLE IF NOT EXISTS questions (
    id          INTEGER PRIMARY KEY,
    event_id    TEXT REFERENCES events(id) ON DELETE CASCADE,
    performer_id TEXT REFERENCES performers(id) ON DELETE CASCADE,
    question    TEXT NOT NULL,
    -- 'open' | 'answered' | 'dismissed'
    status      TEXT NOT NULL DEFAULT 'open',
    answer      TEXT,
    -- What we would do differently once answered.
    impact      TEXT,
    asked_at    TEXT NOT NULL DEFAULT (datetime('now')),
    answered_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_questions_status ON questions(status, asked_at DESC);


-- ---------------------------------------------------------------- semantic search
--
-- Vectors live in their own table keyed by a content hash so re-embedding the
-- same text is a no-op. A separate table (rather than a blob on events) keeps
-- the hot path of a scan free of vector I/O.

CREATE TABLE IF NOT EXISTS embeddings (
    content_hash TEXT PRIMARY KEY,   -- sha256 of the embedded text
    model        TEXT NOT NULL,
    dim          INTEGER NOT NULL,
    vector       BLOB NOT NULL,     -- float32 little-endian
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS event_embeddings (
    event_id     TEXT PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
    content_hash TEXT NOT NULL REFERENCES embeddings(content_hash) ON DELETE CASCADE,
    embedded_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
