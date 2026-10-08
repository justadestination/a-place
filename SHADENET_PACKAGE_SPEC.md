# Shadenet System Specification Sheet
**"A place in the Shade"**
*Version 0.2.0 — Consolidated Package Baseline*

---

## 1. Executive Summary & Architecture

**Shadenet** is an autonomous, privacy-first, zero-trust nightlife intelligence ecosystem designed to operate resiliently across clearnet, darknet, and local mesh networks. It consolidates factual event discovery, four-axis spatial calendar surfaces, peer-to-peer personal agent coordination, cryptographic age verification, and autonomous news syndication into a single containerized distribution.

```
                              ┌─────────────────────────────────────────┐
                              │            SHADENET ECOSYSTEM           │
                              └────────────────────┬────────────────────┘
                                                   │
         ┌───────────────────┬─────────────────────┼─────────────────────┬───────────────────┐
         │                   │                     │                     │                   │
         ▼                   ▼                     ▼                     ▼                   ▼
   ┌───────────┐      ┌─────────────┐       ┌──────────────┐      ┌─────────────┐     ┌─────────────┐
   │ NightCal  │      │   Horizon   │       │ Serendipilyst│      │   Steward   │     │  Towncrier  │
   │ (Calendar)│      │   (Zine)    │       │ (Marketplace)│      │ (Agent PWA) │     │ (Discovery) │
   └─────┬─────┘      └──────┬──────┘       └──────┬───────┘      └──────┬──────┘     └──────┬──────┘
         │                   │                     │                     │                   │
         └───────────────────┴─────────────────────┼─────────────────────┴───────────────────┘
                                                   │
                                                   ▼
                                    ┌─────────────────────────────┐
                                    │    Tri-Sync Mesh Network    │
                                    │ (Primary VPS / Tor / Edge)  │
                                    └─────────────────────────────┘
```

---

## 2. Package Manifest & Component Inventory

### A. Core Engine (`shadenet/`)

| Module / Package | Description & Capabilities | Key Files |
| :--- | :--- | :--- |
| **`shadenet.nightcal`** | **Four-Axis Nightlife Calendar Engine**<br>• Renders interactive event grids across 4 distinct axes.<br>• Dynamic JIT styling via CSS variables (density, themes, scales).<br>• Local voting system (`+1` / `-1` capped tally per client).<br>• Closure detection & source citation integration.<br>• Entity dossier and public agent-card generation. | • `server.py`<br>• `surface.py`<br>• `avr_jit.py`<br>• `fill.py`<br>• `votes.py`<br>• `closures.py`<br>• `agent_events.py`<br>• `agent_cards.py`<br>• `entity_pages.py`<br>• `parse_dao.py`<br>• `social.py`<br>• `social_hardened.py`<br>• `catalog.json`<br>• `static/` |
| **`shadenet.horizon`** | **Umwelt Horizon Autonomous Zine & Syndication**<br>• Markdown vault compiler with AVR (Audio-Visual-Relational) graph generation.<br>• Independent Partner Syndication: embeds badges, credit lines, and canonical URLs for affiliated local press.<br>• Node/Edge relational map output (`nodes.json`, `edges.json`, `avr_graph.json`). | • `zine_pipeline.py`<br>• `vault/`<br>• `nodes/`<br>• `edges/`<br>• `avr_graph.json` |
| **`shadenet.steward`** | **Personal Agent Backend & A2A Airlock**<br>• Agent-to-Agent (A2A) protocol implementation with cryptographic signature validation.<br>• Strict rate-limiting (2 unreplied messages max, tone moderation).<br>• Role contracts (Builder, Researcher, Venue Agent).<br>• Declarative MCP server integration with secret-redacting structured logging.<br>• Task queue and state management. | • `personal_agent.py`<br>• `command_engine.py`<br>• `venue_agent.py`<br>• `inboxes.py`<br>• `public_board.py`<br>• `subscriptions.py`<br>• `mcp-server/server.py`<br>• `mcp-server/logstack.py`<br>• `config/` |
| **`shadenet.towncrier`** | **Factual Discovery & Entity Resolution Store**<br>• SQLite storage engine with change tracking and stable identifier generation.<br>• Entity deduplication and fuzzy match resolution (`rapidfuzz`).<br>• OpenStreetMap Overpass query execution and parser.<br>• Normalization routines for addresses, contacts, social handles, and hours. | • `store.py`<br>• `resolve.py`<br>• `entities.py`<br>• `normalize.py`<br>• `discover.py`<br>• `facts.py`<br>• `schema.sql` |
| **`shadenet.entry`** | **Autonomous Geographic Bootstrap Entrypoint**<br>• Evaluates environment coordinates (`SHADENET_LAT`, `SHADENET_LON`, `SHADENET_RADIUS_KM`).<br>• Computes bounding box, auto-discovers regional venues on first boot, seeds SQLite database, and executes service dispatch (`shadenet`, `fill`, `server`, `zine`). | • `entry.py` |
| **`shadenet.sync_mesh`** | **Tri-Sync Mesh Replicator**<br>• Multi-node state replication across Primary VPS, Tor darknet, and Edge node.<br>• Continuous polling of SQLite changefeeds (`last_insert_rowid`) and Git zine vault commits. | • `sync_mesh.py` |

---

## 3. Container & Infrastructure Topology

### A. Autonomous Container Packaging
- **`Dockerfile`**: Multi-stage OCI image (`build` &rarr; `runtime`).
  - Runtime base: Python with SQLite3, embedded Caddy reverse proxy, and Tor darknet daemon.
  - Zero hardcoded secrets; configuration driven entirely via environment variables.
- **`docker-compose.yml`**:
  - `shadenet`: Core daemon running entrypoint, NightCal server (`8765`), bootstrap crawler, and sync mesh.
  - `caddy`: TLS termination, reverse proxy, and rate-limiting gateway (`80`, `443`).
  - `tor`: Darknet hidden service daemon generating dynamic `.onion` endpoints for unblockable syndication.

### B. Declarative Configuration Files
- `config/caddyfile.caddyconf`: Reverse proxy routes, TLS automation, and static asset caching.
- `config/torrc`: Tor daemon daemon configuration with hidden service directories.
- `config/shadenet.env.example`: Sanitized reference environment template.

---

## 4. Verification & Testing Matrix

The package enforces a 100% passing test baseline across all consolidated subsystems:

| Test Harness | Total Tests | Status | Scope |
| :--- | :---: | :---: | :--- |
| `test_discover.py` | 182 | PASS | OSM Overpass queries, venue discovery, tile clustering, rate-limit isolation |
| `test_nightcal.py` | 122 | PASS | Calendar rendering, 4-axis filtering, JIT CSS, voting engine, closure notes |
| `test_normalize.py` | 59 | PASS | Phone, email, address, website, and social handle canonicalization |
| `test_resolve.py` | 45 | PASS | Multi-source entity resolution, fuzzy matching, deduplication |
| `test_entities.py` | 43 | PASS | Oak entity tree, contact records, stable entity UUIDs |
| `test_social_hardened.py`| 16 | PASS | Zero-trust social citation parsing, anti-hallucination verification |
| `test_scaffold.py` | 58 | PASS | Agent role contracts, A2A envelope signing, MCP server, sandbox isolation |
| **Total Test Suite** | **525** | **100% PASS** | **Complete end-to-end regression validation** |

---

## 5. Sanitization & Anonymization Schema

For distribution and privacy compliance, all site-specific and personal identifiers are abstracted into standard generic placeholders:

| Concrete Identifier Category | Production / Private Instance | Sanitized Distribution Replacement |
| :--- | :--- | :--- |
| **User Identity** | `operator`, `operator@...` | `operator`, `admin@shadenet.internal` |
| **Fleet Node Names** | `node-client`, `node-primary`, `node-inference`, `node-hypervisor`, `node-edge`, `node-storage` | `node-alpha`, `node-primary`, `node-inference`, `node-edge` |
| **Network Addresses** | `10.0.0.*`, `192.168.1.*`, `65.108.*`, `178.105.*` | `10.0.0.*`, `192.168.1.*`, `203.0.113.10`, `198.51.100.20` |
| **Domains & Hostnames** | `*.example.org`, `matrix.example.org` | `*.example.org`, `mesh.internal` |
| **Geographic Municipality** | `Metropolis`, `Valley`, real coordinates | `Metropolis`, `Emerald City`, `(0.0, 0.0)` |
| **Physical Venues & Bars** | Real commercial venues | Fictional venues (*The Neon Foundry, The Grand Roxy, Solstice Cantina*) |
| **Database File** | `shadenet.db` | `shadenet.db` |
