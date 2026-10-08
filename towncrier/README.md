# Towncrier

Towncrier keeps a cited record of downtown Metropolis and serves it as a night sheet. One town, one person, no outbound contact with venues or bands. This directory is the whole project: the sheet, the cited database, the discovery code, and the Hermes agent that writes into it.

To take it somewhere else, copy this directory and nothing else:

```bash
# from the machine that has the project
tar -C /opt/shadenet -czf towncrier.tar.gz towncrier
```

That archive includes `data/shadenet.db` (the rooms, the shows, and the sample tallies). A `git clone` of tracked files also includes that database. Do not leave `data/` behind. `.env` is not in the archive. Copy `.env.example` and fill it in on the new machine.

The public sheet is [https://nightcal.example.org](https://nightcal.example.org).

## What it does

Three pieces, one database.

1. **The oak.** Metropolis is the trunk. Venues are branches. Bands and promoters are leaves. A show is an acorn: it is not stored as an entity. It is inferred by clustering listings. A promoter books rooms through `entity_links` (`rel='books'`), because that is a many-to-many edge, not a field on the room.

2. **The night sheet.** `nightcal` reads that store and draws the month. Resting cells are a short list. Hover or tap opens the day. Inside an open day, four things are visible at once:
   - left to right is the start hour, from 11:00 through 2:00 the next day
   - top to bottom is one lane per show, with a room's shows kept together
   - toward the reader is that show's sample tally against the strongest night on the filtered month
   - the wire along the row is how long the set runs

   Comedy stays pink. Kind is not a fifth axis. Votes are local samples on a cited show, keyed by the listing URL. Up and down are counted separately. The net is ups minus downs. They are not wiped by a restart.

3. **The agent.** Hermes discovers rooms, refuses uncited facts, and can add, correct, or take down a show without deleting the citation underneath it. The declarative Builder/Researcher scaffold and the reviewer skill live in `agent/`.

## How a fact gets onto the sheet

```
OpenStreetMap ──┐
venue's own site ┼─► listings (one row per mention, immutable)
downtown calendar ┤         │
public social page ┘         ▼
                        resolve.py clusters them into events
                                 │
                    surface.py ──┴──► A2UI v0.9 messages
                                 │
                         static/index.html draws the month
```

A fact is publishable only when a public `source_url` backs it. `add_item` raises `UncitedFact` otherwise. Two sources that disagree stay as two linked rows. Nothing is overwritten. One value seen twice is corroboration, not a conflict.

Downtown means Railroad Square through Courthouse Square to Main Street Tavern. The box is `DOWNTOWN_BBOX = (38.428, -122.736, 38.454, -122.698)` in `nightcal/fill.py`. A brewery is not assumed to be a music room. Fill uses the same music-signal classifier as `towncrier/discover.py`.

Rooms come from OpenStreetMap, not Google Places. The Maps Platform terms forbid storing Places content as a system of record. The footer owes OpenStreetMap contributors, and it owes the Downtown Metropolis calendar for the shows. A Facebook, Instagram, or X page is cited only when that page itself lists the show. A login wall adds nothing.

Cited closures stay in the database and drop off the rail unless that room has a cited show. The footnote names the rooms a public notice says have closed. Do not delete a cited listing or a venue row. Prefer `.graveyard/` over removing a file.

## Layout

```
towncrier/          the store and the rules
  schema.sql        entities, items, citations, listings, events
  store.py          sqlite
  entities.py       the tree; UncitedFact lives here
  facts.py          phone, site, and social links from a venue's own pages
  discover.py       OpenStreetMap Overpass
  normalize.py      titles, clocks, DST, performer names
  resolve.py        which listings are the same night
  sources/          source adapters
nightcal/           the sheet and the agent write path
  server.py         HTTP
  surface.py        A2UI v0.9 model
  static/index.html the page
  catalog.json      custom catalog
  fill.py           re-read public rooms and the downtown calendar
  parse_dao.py      the Downtown Metropolis calendar
  social.py         a venue's own site, and public social events only
  closures.py       rooms a public notice says have closed
  votes.py          sample tallies
  agent_events.py   add, correct, take down, without deleting a citation
agent/
  ROADMAP.md        why the Derivee agent exists, and what is unfinished
  scaffold/         Builder + Researcher, YAML plus a stdio MCP server
  skills/           Hermes skills. These are the copies to install.
config/             systemd and Caddy templates
data/               local sqlite, not committed
tests/
scripts/live_check.py   one-tile Overpass probe; do not run the old tiled form
```

`data/shadenet.db` is the live store. It holds the citations and the sample tallies, and it is part of this directory. Sqlite sidecars (`*.db-wal`, `*.db-shm`) are not. Checkpoint the database before you pack the directory if a server is still writing it.

## Use the sheet

From the repo root, with Python 3.11 or newer (this fleet runs 3.14):

```bash
set -a; . ./.env; set +a          # optional; see .env.example
python3 -m nightcal.server
```

Then open `http://127.0.0.1:8765/`. The page is a renderer. It does not know the town until `/api/model` arrives. Reload a tab that was already open.

The server binds `NIGHTCAL_HOST` (comma-separated) on `NIGHTCAL_PORT`. The default is `127.0.0.1:8765`. Set `NIGHTCAL_DB` to point at a different store. The process does not read `.env` itself. Export the variables, or use the systemd unit.

### What the page calls

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/` | the sheet |
| GET | `/catalog.json` | A2UI catalog `https://towncrier.local/catalogs/nightcal/v1/catalog.json` |
| GET | `/api/model` | current data model. Surface id `downtown-nights`. |
| GET | `/api/surface` | full v0.9 message stream, one JSON object per line |
| POST | `/api/action` | UI actions: month, lens, scope, `selectDate`, `vote`, `refresh` |
| POST | `/api/refresh` | same refresh as the action |

`POST /api/action` with `{"name":"refresh"}` re-reads OpenStreetMap and the public calendar. That is `fill()`. Do not run it as a casual check. It writes the store.

`vote` increments the up or down sample for one cited show. Do not send it from a script to "test" the sheet. The tallies are real.

Scope `nights` is shows. Scope `all` also shows food trucks and markets. A restart of the process returns the lens to today and scope `nights`. Votes survive that. They are in the database.

### Install it as a service

`config/nightcal.service` is the unit. On fly the live unit binds `127.0.0.1` and the nebula address `10.0.0.6`, port `8765`, user `shadenet`, working directory this repo.

```bash
sudo cp config/nightcal.service /etc/systemd/system/nightcal.service
# edit WorkingDirectory and NIGHTCAL_HOST first
sudo systemctl daemon-reload
sudo systemctl enable --now nightcal.service
```

### Host it

The name `nightcal.example.org` is a DNS-only A record to the TLS front door `198.51.100.20` (node-gateway). node-gateway terminates Let's Encrypt and proxies HTTP to node-primary (`203.0.113.10:80`). Ardra proxies `Host: nightcal.example.org` to `10.0.0.6:8765`.

`config/caddy-frontend.snippet` is the node-gateway site block. `config/caddy-backend.snippet` is the node-primary site block. Append them. Do not replace a running Caddyfile with either snippet. Ardra is NixOS: a rebuild restores the store Caddyfile and drops a hand-edited route until it is appended again.

The vote and events API is on the same public host as the page.

## Use the agent

An agent writes shows through HTTP. Every write needs a public page that lists the show. The server stores that listing on the `agent` source, then resolution turns it into the event the sheet shows. A correction sits beside the original listing. The sheet prefers the correction. Taking a show down records the change and leaves the listing row.

Create:

```bash
curl -s -X POST http://127.0.0.1:8765/api/events \
  -H 'content-type: application/json' \
  -d '{
    "title": "Name as printed on the cited page",
    "startsAt": "2026-10-10T20:00:00-07:00",
    "endsAt": "2026-10-10T22:00:00-07:00",
    "sourceUrl": "https://example.com/the-public-listing",
    "venue": "Shady Oak Barrel House",
    "kind": "music"
  }'
```

`title`, `startsAt`, and `sourceUrl` are required. `sourceUrl` must be a public `http` or `https` URL. Optional fields: `endsAt`, `venue`, `venueId`, `kind` (`music`, `comedy`, `show`, `trivia`, `other`, `trucks`, `market`), `status` (`EventScheduled`, `EventCancelled`, `EventPostponed`, `EventRescheduled`), `description`, `externalId`.

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/events` | list. Filters: `date`, `venueId`, `kind`, `hidden=1` |
| GET | `/api/events/{id}` | one show. Ids look like `evt_` plus 16 hex digits |
| POST | `/api/events` | create. 201 the first time, 200 if that external id already existed |
| PATCH | `/api/events/{id}` | correct. Sends only the fields that changed, plus `sourceUrl` when the citation changes |
| DELETE | `/api/events/{id}` | take down. Body may include `sourceUrl` and `reason` |

Do not invent a venue name, a phone number, or a date. If the room is not already in the store, pass `venue` only when the cited page names it. Missing-venue listings stay with no venue id.

### Hermes skills

Install the project skills by pointing Hermes at this repo:

```bash
ln -sfn /opt/shadenet/towncrier/agent/skills/towncrier-event-discovery \
  ~/.hermes/skills/project/towncrier-event-discovery
ln -sfn /opt/shadenet/towncrier/agent/skills/derivee-agent-scaffold \
  ~/.hermes/skills/project/derivee-agent-scaffold
```

`agent/skills/towncrier-event-discovery/SKILL.md` is the discovery and sheet contract. `agent/skills/derivee-agent-scaffold/SKILL.md` is the MCP scaffold. `agent/skills/scaffold-reviewer/` is the skill Hermes uses to review a small YAML agent scaffold. `agent/ROADMAP.md` is the map of that scaffold: local model first, Matrix when a real room exists, no keys in the files.

### Run the scaffold

```bash
cd agent/scaffold
python3 -m pip install -r mcp-server/requirements.txt
./instantiate.sh
```

`config/agent.yaml` points local inference at Ollama, `http://127.0.0.1:11434`, model `hermes-3-llama-3.1-8b`. Change the model name if that quant is not installed. Cloud fallback reads `CLOUD_API_KEY` from the environment when a task actually escalates. `config/matrix.yaml` is placeholders. The token is `MATRIX_ACCESS_TOKEN`. With it unset, `matrix_signal` returns success with `sent` false. That is the unconfigured state, not a crash.

The MCP server speaks JSON-RPC on stdout. Do not print from a tool handler. Logs go to stderr. `AGENT_STDOUT_GUARD=1` breaks the transport. Leave it unset.

## Tests

```bash
python3 tests/test_entities.py
python3 tests/test_normalize.py
python3 tests/test_resolve.py
python3 tests/test_discover.py
python3 tests/test_nightcal.py

cd agent/scaffold
python3 test_scaffold.py
python3 test_integration.py
python3 test_mcp_client.py
```

## Configuration

Copy `.env.example` to `.env`. Nothing in the example is a secret. Real tokens stay in the environment of the machine.

| Variable | Used by | Default |
| --- | --- | --- |
| `NIGHTCAL_HOST` | `nightcal.server` | `127.0.0.1` |
| `NIGHTCAL_PORT` | `nightcal.server` | `8765` |
| `NIGHTCAL_DB` | `nightcal.server` | `data/shadenet.db` |
| `MATRIX_ACCESS_TOKEN` | agent scaffold | unset means not configured |
| `CLOUD_API_KEY` | agent scaffold, only on escalation | unset |
| `AGENT_LOG_LEVEL` | agent scaffold | `INFO` |
| `AGENT_LOG_FORMAT` | agent scaffold | text; `json` for JSON on stderr |
| `AGENT_LOG_FILE` | agent scaffold | `state/logs/agent.log`; empty disables the file |
| `AGENT_STDOUT_GUARD` | agent scaffold | `0`. Do not set it to `1` |

Other files an operator actually edits:

| File | What it is |
| --- | --- |
| `.env.example` | every variable above, commented |
| `config/nightcal.service` | systemd unit |
| `config/caddy-backend.snippet` | HTTP reverse proxy on node-primary |
| `config/caddy-frontend.snippet` | TLS site on node-gateway |
| `agent/scaffold/config/agent.yaml` | roles, local model, escalation |
| `agent/scaffold/config/matrix.yaml` | homeserver placeholders, no token |
| `agent/scaffold/config/lexicon.yaml` | shared words |
| `agent/scaffold/config/tasks.yaml` | seed tasks T001–T004 |
| `agent/scaffold/config/mcp-tools.yaml` | the five tool declarations |

Clocks in the sheet are America/Los_Angeles. DST is per date, through `zoneinfo`, not a fixed offset.
