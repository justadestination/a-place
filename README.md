# ShadeNet: a place in the shade

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](#run-it)

**NightCal** is a night calendar for a city's shows, venues and events. It fills
itself from primary sources (OpenStreetMap, venues' own sites and calendars),
cites every fact, and is free for anyone to read: no account, no cookies, no
tracking. It exists because event discovery got buried inside social media
feeds.

**ShadeNet** is the platform around it. NightCal and the zine, *Umwelt
Horizons*, are public. Everything else (posting, voting, submitting, the
Serendipilyst board, messaging) goes through a **Steward**: a personal agent
on the user's phone, activated with an over-21 proof. We know which Steward
someone is with, never who they are.

> **Status: early and moving.** This is a working tree, not a release. Some
> modules are prototypes, and the test suites currently have failures (see
> [Tests](#tests)).

---

## What's here

| Part | Where | What it does |
|---|---|---|
| **NightCal** | `shadenet/nightcal/` | Calendar server and model: venues, events, lifecycle, time zones, iCal feeds, vote tallies, closures, venue pages. Serves the site and `/api/*`. |
| **Towncrier** | `shadenet/towncrier/`, `towncrier/` | The cited fact store: OpenStreetMap discovery, normalisation, entity resolution, SQLite storage. A fact without a source isn't stored. |
| **Umwelt Horizons** | `shadenet/horizon/`, `zine/`, `zine-automation/` | The zine: a markdown vault compiled into a linked graph, plus the newsroom pipeline and its editorial charter. |
| **Serendipilyst** | `shadenet/serendipilyst/` | Community board for services, gigs and notices. Steward-gated. |
| **Steward (earlier version)** | `shadenet/steward/` | The first Steward: agent roles, MCP server, client scripts. Its rules engine is being rebuilt as a separate project. |
| **Platform** | `shadenet/*.py`, `shadenet/ops/` | Auth, rate limits, health, backups, flags, search, chat, operator console. |
| **Front end** | `web/`, `tokens/`, `design-system/` | Plain ES modules and CSS, no framework, no runtime build. Start with `web/README.md`. |
| **Deploy** | `deploy/`, `Dockerfile`, `docker-compose.yml` | Container and server provisioning scripts. |
| **Docs** | `docs/` | Architecture, decisions (`docs/decisions/`), accessibility and performance audits. |

Specifications: `SHADENET_SPEC.md`, `SHADENET_PACKAGE_SPEC.md`, `SHADENET_PLAN.md`,
`ROADMAP.md`, `TODO.md`. Some of these describe plans that have since changed
(for example, Monero support was dropped; a few references remain in `deploy/`
and `web/`).

---

## Run it

Python 3.11 or newer. The core server uses the standard library and SQLite.

```bash
python3 -m shadenet.nightcal.server      # then open http://127.0.0.1:8765
python3 -m shadenet.nightcal.fill        # discover venues and fill the calendar
```

| Variable | Default | Purpose |
|---|---|---|
| `NIGHTCAL_PORT` | `8765` | Port for the calendar server. |
| `NIGHTCAL_HOST` | `127.0.0.1` | Interfaces to bind, comma-separated. |
| `NIGHTCAL_DB` | `shadenet/data/shadenet.db` | SQLite store. |
| `SHADENET_DEV_MODE` | `0` | `1` uses test age attestations, for development and CI. Never set in production. |

The container entry point (`shadenet/entry.py`) also reads these. Discovery on
boot runs only when all three location variables are set; there are no defaults.

| Variable | Purpose |
|---|---|
| `SHADENET_LAT`, `SHADENET_LON` | Centre of the discovery area. |
| `SHADENET_RADIUS_KM` | Radius of the discovery area, in kilometres. |
| `SHADENET_DB` | SQLite store for the container (default `data/shadenet.db`). |

Front-end pages are static files built by `web/tools/build_pages.py`. Some files
in `web/` are build outputs, so check `web/README.md` before editing them by hand.

---

## Tests

```bash
python3 -m pytest -q tests                              # platform and API
for f in towncrier/tests/test_*.py; do PYTHONPATH=. python3 "$f"; done   # fact store
(cd shadenet/steward && python3 test_scaffold.py)       # earlier Steward
node web/tests/run.mjs                                  # front end (needs Chromium)
```

Last run, 13 October 2026:

| Suite | Passed | Failed |
|---|---:|---:|
| `tests/` | 214 (1 skipped) | 1: `test_ops.py::test_network_allowlist` |
| `towncrier/tests/` | 460 | 7, all in `test_nightcal.py` |
| `shadenet/steward/test_scaffold.py` | 58 | 0 |
| `web/tests/` | not run | |

---

## Layout

```text
shadenet/            runtime package: nightcal, towncrier, horizon, serendipilyst, steward, platform modules
towncrier/           fact-store compatibility layer and its test scripts
web/                 front end: pages, components, embeds, PWA files, tests
tokens/              design tokens and themes (contrast-checked at build)
design-system/       design system source and artifact
zine/                zine graph data
zine-automation/     newsroom pipeline, personas, charter, runbooks
deploy/              server provisioning and container scripts
docs/                architecture, decisions, audits
tests/               Python test suite
agent-scaffold/      agent role templates and MCP configuration
scaffold-reviewer/   review skill for small scaffolded codebases
tools/, config/, data/, state/
```

---

## License

Apache License 2.0. See [LICENSE](LICENSE).
