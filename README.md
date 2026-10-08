# Shadenet (A place in the Shade)

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Tests: 525 passed](https://img.shields.io/badge/Tests-525%20passed-brightgreen.svg)](#test-suite--verification)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](#prerequisites)
[![Architecture: Zero--Surveillance](https://img.shields.io/badge/Privacy-Zero--Surveillance-purple.svg)](#architecture--philosophy)

**Shadenet** is an autonomous, privacy-first nightlife intelligence ecosystem and decentralized cited intelligence network. It provides four-axis spatial calendar views, sovereign personal agent coordination, cryptographic age verification, primary-source venue discovery, and autonomous news syndication designed to run across clearnet, darknet, and local mesh networks.

---

## Table of Contents

- [Architecture & Philosophy](#architecture--philosophy)
- [System Taxonomy & Core Capabilities](#system-taxonomy--core-capabilities)
  - [1. NightCal (The 4-Axis Calendar)](#1-nightcal-the-4-axis-calendar)
  - [2. Steward (Personal Agent & PWA)](#2-steward-personal-agent--pwa)
  - [3. Substrate (The Governed Render Layer)](#3-substrate-the-governed-render-layer)
  - [4. Umwelt Horizon (The Autonomous Zine)](#4-umwelt-horizon-the-autonomous-zine)
  - [5. Serendipilyst (The Bulletin & Marketplace)](#5-serendipilyst-the-bulletin--marketplace)
  - [6. Towncrier (Discovery & Entity Resolution)](#6-towncrier-discovery--entity-resolution)
  - [7. Tri-Sync Mesh Network](#7-tri-sync-mesh-network)
- [Quick Start](#quick-start)
- [Configuration & Environment Variables](#configuration--environment-variables)
- [Test Suite & Verification](#test-suite--verification)
- [Repository Structure](#repository-structure)
- [License](#license)

---

## Architecture & Philosophy

Shadenet operates on two fundamental principles:

1. **Zero Surveillance, Full Citation:** Every venue, show, contact handle, and phone number is backed by primary-source citations (OpenStreetMap, official websites, cited event feeds). No third-party ad pixels, trackers, or commercial profiling.
2. **Two-Tier Access Model:**
   - **Public Read (Above Sea Level):** The clearnet web surface is 100% read-only. Anyone can inspect NightCal calendars and read Umwelt Horizon zines without an account, cookies, or tracking.
   - **Gated Write (Below Sea Level):** All state mutations (voting `+1`/`-1`, bulletin postings, direct messages, zine submissions) must pass through a verified **Steward** bound to a Zero-Knowledge 21+ Proof.

```
┌────────────────────────────────────────────────────────────────────────┐
│                              SHADENET                                  │
├────────────────────────────────────────────────────────────────────────┤
│  ABOVE SEA LEVEL (Public Read Surfaces):                               │
│    - NightCal         ──► 4-Axis Spatial Responsive Night Calendar     │
│    - Umwelt Horizon   ──► Zine (Editorial, Reviews & Syndication)      │
├────────────────────────────────────────────────────────────────────────┤
│  THE GATES:                                                            │
│    - Steward          ──► Sovereign Personal Agent PWA on Device       │
│                           with A2A Mailbox, Local Calendar & ZKP 21+   │
├────────────────────────────────────────────────────────────────────────┤
│  BELOW SEA LEVEL (Engines, Marketplace & Mesh):                        │
│    - Serendipilyst    ──► Marketplace (Services, Board Posts, Gigs)    │
│    - Rooms            ──► Physical Hosts & Venues (OSM-cited entities) │
│    - Flags            ──► Public Agent Cards & Venue Dossiers          │
│    - Tri-Sync Mesh    ──► Primary VPS ◄► Tor (.onion) ◄► Local Mesh Pi │
└────────────────────────────────────────────────────────────────────────┘
```

---

## System Taxonomy & Core Capabilities

### 1. NightCal (The 4-Axis Calendar)

A dense, high-legibility night sheet for metropolitan music and arts listings:

- **4-Axis Spatial Layout:**
  - **X-Axis:** Start hour (chronological time progression).
  - **Y-Axis:** Venue lanes (clustered geographically by room).
  - **Z-Axis:** Community sample tally (verified `+1` / `-1` consensus).
  - **Wire (Duration):** Estimated set duration vector.
- **A2UI Live Streaming:** Server pushes streaming component projection messages over HTTP JSONL; the client dynamically renders without full page reloads.
- **Closure Detection:** Automatically flags and cites permanent or seasonal venue closures directly on listings.
- **Vote Consensus Engine:** One-vote-per-agent tallying with cryptographic key signatures.

### 2. Steward (Personal Agent & PWA)

A sovereign client-side agent running locally in browser storage (PWA):

- **ZKP 21+ Gate:** Evaluates age verification via the W3C Digital Credentials API (`navigator.identity.get()`) requesting selective disclosure (`age_over_21: true`) from mobile driver's licenses (mDL ISO 18013-5 / Apple Wallet / Google Wallet). Personal identity, name, and address remain private on device.
- **A2A Key Binding:** Cryptographically binds verification attestations to the Steward's local `a2a://agent/personal_<uuid>` public key, preventing token transfer or replay.
- **Personal Calendar & Skills Registry:**
  - Local calendar managing private appointments, pinned shows, and availability windows.
  - `#tag` service declarations (`#soundtech`, `#bartender`, `#lighting`).
  - Peer queries ("Find an available sound tech this Friday") matching peer public Flags without ad brokers.
- **Transparent Explainability Log:** Audit-visible learned user model (`#inference-log`). When users adjust choices, corrections append as higher-confidence rules rather than secretly overwriting previous entries. Exportable as JSON.
- **Conversational Guardrails:**
  - **2-Message Cap:** Automatically pauses outbound messaging after 2 consecutive unreplied messages to a peer.
  - **Tone Review:** Identifies aggressive language and requests conversational rephrasing before dispatch.
  - **Adaptive Content Filters:** Prompts with persistent options (*View Once*, *Always allow from sender*, *Always allow category*).

### 3. Substrate (The Governed Render Layer)

A client-side contract engine enforcing accessibility and clutter ceilings on the live DOM:

- **Mathematical Contrast Floors:** Live WCAG 2.x relative luminance checks on all text elements against policy floors (up to 8:1 / 9:1 minimum contrast).
- **Hard Surface Refusal:** If a computed contrast floor or clutter ceiling is breached, Substrate refuses to render the surface rather than quietly shipping a broken or low-contrast UI.
- **Motion Gating:** Enforces `prefers-reduced-motion` and locks parallax/autoplay animations unless explicitly requested.
- **Touch Gesture Calibration:** Calibrated swipe and tap detection (`gestures.js`) disambiguating single taps, intentional zoom, and reading progression.

### 4. Umwelt Horizon (The Autonomous Zine)

A decentralized editorial publication and news syndication engine:

- **Markdown Vault Compiler:** Compiles a Git-backed markdown vault into an Adaptive Viewport Resolution (AVR) relational graph (`nodes.json`, `edges.json`, `avr_graph.json`).
- **Wikilink Resolution:** Statically validates and links inter-article `[[wikilinks]]`.
- **Independent Partner Syndication:** Articles flagged with `type: syndicated` render with partner badges, original author attributions, and canonical origin URLs.

### 5. Serendipilyst (The Bulletin & Marketplace)

A privacy-centric community board for services, equipment sharing, and gig postings:

- Gated write operations requiring an activated, verified Steward.
- Rate-limited submission cooldowns to eliminate automated commercial spam.
- Anonymous and pseudonymous listing modes.

### 6. Towncrier (Discovery & Entity Resolution)

The underlying factual discovery and resolution engine:

- **OpenStreetMap Overpass Scraper:** Queries venue metadata, address tags, wheelchair accessibility, opening hours, and music signals directly from OSM.
- **Entity Resolution Engine:** Deduplicates disparate venue records, websites, and promoter feeds using fuzzy string matching (`rapidfuzz`) and deterministic UUID hashing (`stable_id`).
- **Normalization Pipeline:** Cleanses performer names, parses ISO datetime strings, canonicalizes phone numbers and emails, and validates primary sources.
- **SQLite Storage:** Transactional ACID store with strict schema definitions (`schema.sql`), fact tables, and source audit trails.

### 7. Tri-Sync Mesh Network

A three-tier resilient network topology:

- **Primary Node (Clearnet):** Hosted on cloud VPS behind Caddy with automatic TLS and privacy headers (`Referrer-Policy: no-referrer`, client IP redaction).
- **Darknet Fallback (Tor):** Onion service daemon (`.onion`) providing censorship-resistant access.
- **Edge Node (Local Mesh):** Raspberry Pi node operating on a local physical mesh network.
- **State Synchronization:** Background sync routines replicating SQLite changefeeds and git zine commits across nodes.

---

## Quick Start

### Prerequisites

- **Python:** 3.11 or newer (standard library only for core calendar & server).
- **SQLite:** 3.35+ (bundled with standard Python).

### 1. Clone the Repository

```bash
git clone https://github.com/justadestination/a-place.git
cd a-place
```

### 2. Start the NightCal Server

Run the standalone calendar server directly from the repository root:

```bash
python3 -m shadenet.nightcal.server
```

Open your browser to:
```text
http://127.0.0.1:8765
```

### 3. Run Autonomous Venue Discovery & DB Fill

To query regional venues from OpenStreetMap and populate listings into SQLite:

```bash
python3 -m shadenet.nightcal.fill
```

### 4. Run the Full Test Suite

Execute the towncrier and scaffold verification test suites:

```bash
# Run the 467 towncrier discovery & entity tests
for f in test_discover.py test_entities.py test_nightcal.py test_normalize.py test_resolve.py test_social_hardened.py; do
    PYTHONPATH=. python3 towncrier/tests/$f || exit 1
done

# Run the 58 scaffold & sandboxing tests
cd shadenet/steward && python3 test_scaffold.py
```

---

## Configuration & Environment Variables

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `NIGHTCAL_PORT` | `8765` | TCP port for the HTTP calendar server. |
| `NIGHTCAL_HOST` | `127.0.0.1` | Comma-separated bind host interfaces. |
| `NIGHTCAL_DB` | `shadenet/data/shadenet.db` | Custom path to the SQLite store file. |
| `SHADENET_DEV_MODE` | `0` | Set `1` to bypass live W3C mDL biometrics for CI and local testing. |
| `SHADENET_LAT` | `38.4404` | Center latitude for autonomous Overpass discovery bounding box. |
| `SHADENET_LON` | `-122.7141` | Center longitude for autonomous Overpass discovery bounding box. |
| `SHADENET_RADIUS_KM`| `5.0` | Search radius in kilometers for Overpass venue discovery. |

---

## Test Suite & Verification

Shadenet maintains a strict 100% pass requirement across 525 unit, integration, and sandbox tests:

| Test Harness | Test Count | Status | Focus Areas |
| :--- | :---: | :---: | :--- |
| `test_discover.py` | 182 | **PASS** | OSM Overpass querying, tile clustering, rate-limit isolation |
| `test_nightcal.py` | 122 | **PASS** | Calendar grid math, 4-axis filtering, JIT CSS, voting engine |
| `test_normalize.py` | 59 | **PASS** | Phone/email/address normalizers, performer name splitting |
| `test_resolve.py` | 45 | **PASS** | Fuzzy venue deduplication, multi-source conflict resolution |
| `test_entities.py` | 43 | **PASS** | Oak entity store, contact records, stable entity UUIDs |
| `test_social_hardened.py` | 16 | **PASS** | Zero-trust social citation parsing, anti-hallucination checks |
| `test_scaffold.py` | 58 | **PASS** | Agent role contracts, A2A envelope signing, MCP sandbox |
| **Total Test Suite** | **525** | **100% PASS** | **Complete end-to-end regression validation** |

---

## Repository Structure

```text
a-place/
├── shadenet/                   # Unified Shadenet runtime package
│   ├── nightcal/               # NightCal server, views, votes & static assets
│   │   ├── server.py           # HTTP server & A2UI JSONL dispatcher
│   │   ├── surface.py          # Calendar layout & projection engine
│   │   ├── fill.py             # OSM Overpass & calendar crawler
│   │   ├── votes.py            # Consensus voting engine
│   │   └── static/             # Frontend HTML, CSS, Steward & Substrate scripts
│   ├── horizon/                # Umwelt Horizon zine markdown vault & AVR graph
│   │   └── vault/              # Markdown articles, reviews, and checklists
│   ├── steward/                # Personal Agent backend, MCP server & contracts
│   │   ├── client/             # Vanilla JS client engine (steward.js, substrate.js)
│   │   ├── command_engine.py   # Rate limiting & attestation verification
│   │   ├── personal_agent.py   # A2A personal agent state machine
│   │   ├── test_scaffold.py    # 58-test comprehensive harness
│   │   └── roles/              # Declarative agent role specifications
│   ├── towncrier/              # Factual store, entity resolution & citations
│   │   ├── store.py            # SQLite engine with audit tracking
│   │   ├── resolve.py          # Entity clustering & deduplication
│   │   └── discover.py         # OpenStreetMap crawler
│   └── data/                   # Default SQLite database location (shadenet.db)
├── towncrier/                  # Compatibility shim & legacy test suite
│   └── tests/                  # 467 baseline verification tests
├── agent-scaffold/             # Scaffolding role templates & MCP configurations
├── LICENSE                     # Apache 2.0 License
├── SHADENET_SPEC.md            # Master architectural specification
└── SHADENET_PACKAGE_SPEC.md    # Component manifest and technical audit
```

---

## NightCal Front-End & Design System (`web/`, `tokens/`)

The public calendar and the AVR+JIT zine have a token-based design system and a static front-end in `web/`. It reads the existing `/api/model` and changes nothing in the backend.

- **Tokens and themes:** `tokens/` holds the canonical light and dark themes. Both are gated to WCAG 2.2 AA at build time.
- **Components:** 15 components, each with a standalone `/embed/<name>/` route, social metadata and a README.
- **Theme API:** live, contrast-enforced theming for Steward agents. See `docs/THEME_API.md`.
- **Pages:** the redesigned calendar (`/`), the zine node map (`/zine/`), a 3D/WebXR preview (`/3d/`), a design system gallery (`/system/`) and three landing options waiting on the owner (`/landing/`).
- **Start here:** `web/README.md`. The audits are in `docs/AUDIT.md` (legacy page) and `docs/ACCESSIBILITY.md` (this layer).

## License

This project is licensed under the **Apache License, Version 2.0**. See the [LICENSE](LICENSE) file for details.
