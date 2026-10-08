# Shadenet Execution Todo-List
**"A place in the Shade"**

Canonical task tracker for transforming the Derivee/Towncrier prototype into the unified, autonomous **Shadenet** system.

---

## Progress Overview

- [x] **Phase 0:** Foundational Scaffold, Declarative MCP Server & Initial Database (Completed)
- [x] **Phase 1:** Per-Agent Inboxes, Hardened Social Citations, Zine Pipeline & AVR+JIT (Completed)
- [x] **Phase 2:** Structural Package Unification & Containerization
  - [x] **TASK-01: Monorepo Consolidation** — shadenet/nightcal, shadenet/horizon, shadenet/steward; all 467 towncrier + 58 scaffold tests pass
  - [x] **TASK-02: Autonomous Single-Container Packaging** — multi-stage Dockerfile + docker-compose.yml (Python 3.11, Caddy, Tor, SQLite); dynamic geographic bootstrap (SHADENET_LAT/LON/RADIUS_KM); sync_mesh.py for tri-node replication
- [ ] **Phase 3:** Steward Core Engine, ZKP 21+ Gate & Adaptive Memory
- [ ] **Phase 4:** Unified Multi-View UI (NightCal, Umwelt Horizon, Serendipilyst, Flags)
- [ ] **Phase 5:** Hardened A2A Airlock, Moderation & Anti-Abuse
- [ ] **Phase 6:** Autonomous Geographic Discovery Bootstrapping
- [ ] **Phase 7:** Tri-Sync Multi-Node Mesh (Hetzner, Cloudflare, Tor, Raspberry Pi)
- [ ] **Phase 8:** End-to-End Integration & Acceptance Verification

---

## Phase 2: Structural Package Unification & Containerization

- [ ] **TASK-01: Monorepo Consolidation**
  - **Objective:** Reorganize loose top-level directories ([`towncrier/`](file:///home/operator/Downloads/Derivee/towncrier), [`agent-scaffold/agent-scaffold/`](file:///home/operator/Downloads/Derivee/agent-scaffold/agent-scaffold), [`towncrier/zine/`](file:///home/operator/Downloads/Derivee/towncrier/zine)) into a unified Python package namespace `shadenet/`:
    - `shadenet.nightcal` (Calendar engine & server)
    - `shadenet.horizon` (Zine compiler & vault)
    - `shadenet.serendipilyst` (Marketplace & boards)
    - `shadenet.steward` (Agent backend & A2A protocol)
  - **Verification:** All 467 towncrier tests and 58 scaffold tests run and pass under the new namespace.

- [ ] **TASK-02: Autonomous Single-Container Packaging**
  - **Objective:** Create a multi-stage production [`Dockerfile`](file:///home/operator/Downloads/Derivee) and `docker-compose.yml` packaging:
    - Python 3.14 runtime with dependencies
    - SQLite database (`shadenet.db`)
    - Embedded Caddy reverse proxy
    - Tor daemon (for automated `.onion` hidden service generation)
  - **Verification:** `docker compose up` starts cleanly, binds the local ports, generates a `.onion` hostname in `/var/lib/tor/shadenet/hostname`, and serves the calendar.

---

## Phase 3: Steward Core Engine, ZKP 21+ Gate & Adaptive Memory

- [ ] **TASK-03: PWA Shell & Static Assets**
  - **Objective:** Implement `manifest.webmanifest`, application icons, and an offline Service Worker (`sw.js`) inside the web static directory.
  - **Verification:** Chrome / Safari mobile devtools report a valid installable PWA with offline caching enabled.

- [ ] **TASK-04: Client-Side Steward Engine (`steward.js`)**
  - **Objective:** Implement the browser-based personal agent in vanilla JavaScript:
    - Generate and persist `a2a://agent/personal_<uuid>` address and cryptographic Ed25519 keypair in `localStorage`/`IndexedDB`.
    - Provide cryptographic signing for outbound A2A JSON-RPC envelopes.
  - **Verification:** Unit tests confirm keys and signed envelopes match [`command_engine.py`](file:///home/operator/Downloads/Derivee/agent-scaffold/agent-scaffold/command_engine.py) signature validation.

- [ ] **TASK-05: Zero-Knowledge Proof 21+ Gate**
  - **Objective:** Implement cryptographic age verification using the W3C Digital Credentials API:
    - Client requests selective disclosure of `{ age_over_21: true }` from mobile wallets (Apple Wallet, Google Wallet, mDL ISO 18013-5).
    - Bind the issuer's signature to the Steward's local `a2a://` public key to create a non-transferable Attestation Token.
    - Implement a developer mock mode (`SHADENET_DEV_MODE=1`) for local CI and unit testing.
  - **Verification:** Simulated and live mDL attestation tokens successfully validate in [`command_engine.py`](file:///home/operator/Downloads/Derivee/agent-scaffold/agent-scaffold/command_engine.py).

- [ ] **TASK-06: Verbose Explanations Engine**
  - **Objective:** Add an explanation dialog generator into the Steward UI for all rule limits:
    - 2-Message unreplied limit explanation
    - Outbound tone/civility pause dialog
    - Vote capping explanation (+1 / -1 maximum)
    - Marketplace cooldown timer countdown
    - 21+ age gate activation guidance
  - **Verification:** Triggering any restriction renders conversational, actionable explanations rather than bare error codes.

- [ ] **TASK-07: Adaptive Choice-Based Memory**
  - **Objective:** Build local preference learning for content advisories:
    - Inbound content warnings offer: `[View Once]`, `[Always allow from this sender]`, `[Always allow this category]`, `[Always discard]`.
    - Persist user decisions in on-device storage (`steward_rules`).
    - Automatically apply learned rules to subsequent incoming messages and feed items.
    - Provide a Settings UI to view, edit, and reset learned preferences.
  - **Verification:** Selecting "Always allow" passes future matching items without prompt; resetting rules restores prompts.

- [ ] **TASK-08: Personal Calendar & Skills Directory**
  - **Objective:** Implement local personal calendar and skills registry in the Steward:
    - Private personal calendar storing private events and pinned NightCal shows.
    - Configurable "Available Times" (e.g. `Weekends 17:00–21:00`).
    - Tagged "Available For" skills registry (e.g. `#plumber`, `#soundtech`, `#bartender`).
    - Local tag search engine allowing peer lookups.
  - **Verification:** Adding an event stores it locally; peer skill search returns matching Flags.

---

## Phase 4: Unified Multi-View UI (NightCal, Horizon, Serendipilyst, Flags)

- [ ] **TASK-09: Unified Interface Navigation Shell**
  - **Objective:** Expand [`nightcal/static/index.html`](file:///home/operator/Downloads/Derivee/towncrier/nightcal/static/index.html) into an integrated responsive mobile-first shell with tabbed navigation:
    - **NightCal Tab:** The 4-axis interactive night calendar.
    - **Umwelt Horizon Tab:** Zine node-graph viewer and markdown article reader.
    - **Serendipilyst Tab:** Community bulletin board and marketplace listings.
    - **Flags Tab:** Profile directory for Rooms (venues) and public Stewards.
  - **Verification:** Seamless client-side navigation between all four views without full page reloads.

- [ ] **TASK-10: Umwelt Horizon News Syndication**
  - **Objective:** Update [`nightcal/zine_pipeline.py`](file:///home/operator/Downloads/Derivee/towncrier/nightcal/zine_pipeline.py) to support `type: syndicated`:
    - Frontmatter supports `partner_name`, `original_url`, `author`, `license`.
    - Render syndicated posts with an "Independent Partner Syndication" badge and canonical link.
  - **Verification:** Test zine entry with `type: syndicated` compiles into `nodes.json` and renders badge in UI.

- [ ] **TASK-11: Public Flags Profile Builder**
  - **Objective:** Allow users to build and publish an optional public Flag (Agent Card):
    - Configurable bio, declarations to the world, public A2A/PGP address, availability slots, and skills tags.
    - Privacy toggle: choose whether it links to your marketplace postings or remains anonymous.
  - **Verification:** Exported Flag renders cleanly as static HTML and displays in the Flags directory.

- [ ] **TASK-12: Expanded JIT Layout & Localization Engine**
  - **Objective:** Extend [`nightcal/avr_jit.py`](file:///home/operator/Downloads/Derivee/towncrier/nightcal/avr_jit.py) concepts to client-side CSS & JS:
    - Dynamic CSS variable scaling (`--font-scale`, `--layout-density`, `--theme-contrast`, `--accent-color`).
    - Multi-language dictionary layer for UI strings.
  - **Verification:** Changing density, theme, or language applies immediately without server round-trip.

---

## Phase 5: Hardened A2A Airlock, Moderation & Anti-Abuse

- [ ] **TASK-13: Gated Server Ingress (`/api/a2a`)**
  - **Objective:** Harden [`nightcal/server.py`](file:///home/operator/Downloads/Derivee/towncrier/nightcal/server.py):
    - Public web requests (`GET /`, `GET /api/model`, `GET /api/surface`) remain strictly read-only.
    - Remove raw unauthenticated vote path (`POST /api/action {"name":"vote"}`).
    - Route all mutations through `POST /api/a2a` requiring valid A2A JSON-RPC envelopes with 21+ ZKP attestation headers.
  - **Verification:** Unauthenticated POSTs return 403; valid signed A2A envelopes execute correctly.

- [ ] **TASK-14: Command Engine Abuse & Rate Limits**
  - **Objective:** Implement server-side verification in [`command_engine.py`](file:///home/operator/Downloads/Derivee/agent-scaffold/agent-scaffold/command_engine.py):
    - Enforce exactly one vote (`+1` or `-1`) per event per agent address.
    - Enforce rate-limits on `board.post` and `event.create`.
    - Verify 21+ cryptographic attestation token on every mutation.
  - **Verification:** Double-voting or rapid-fire posting is rejected with structured error codes.

---

## Phase 6: Autonomous Geographic Discovery Bootstrapping

- [ ] **TASK-15: Dynamic Coordinate & Radius Seeding**
  - **Objective:** Update [`towncrier/discover.py`](file:///home/operator/Downloads/Derivee/towncrier/towncrier/discover.py) and [`fill.py`](file:///home/operator/Downloads/Derivee/towncrier/nightcal/fill.py):
    - Read environment variables `SHADENET_LAT`, `SHADENET_LON`, `SHADENET_RADIUS_KM` (or CLI flags).
    - Dynamically calculate latitude/longitude bounding boxes from center coordinates and radius.
    - Run Overpass discovery and initialize fresh database on container first boot.
  - **Verification:** Running with test coordinates (e.g. Petaluma or Sebastopol) automatically seeds the database with local venues.

- [ ] **TASK-16: Venue Minimum Age Tagging**
  - **Objective:** Update schema and discovery classifier:
    - Add `min_age` (INTEGER: `0`, `18`, `21`) to `venues` and `events` in [`schema.sql`](file:///home/operator/Downloads/Derivee/towncrier/towncrier/schema.sql).
    - Classify bars/breweries as 21+, theatres/parks as 0.
  - **Verification:** Newly discovered venues and events carry appropriate `min_age` integers in SQLite.

---

## Phase 7: Tri-Sync Multi-Node Mesh

- [ ] **TASK-17: Tri-Node Synchronization Script (`sync_mesh.py`)**
  - **Objective:** Create a background state synchronization daemon:
    - Syncs SQLite changes (listings, verified sample votes, entity links) between Primary (Hetzner VPS), Darknet (Tor Hidden Service), and Hyper-Local (Raspberry Pi).
    - Pulls and merges git-tracked zine vault updates.
  - **Verification:** A vote or event added on the local node replicates to the VPS within the sync interval.

- [ ] **TASK-18: Production Caddy Ingress Hardening**
  - **Objective:** Finalize the Caddy configuration snippets for Hetzner and Cloudflare:
    - Strip server identity headers (`Server`, `X-Powered-By`).
    - Drop all `/api/events*` and unauthenticated action requests at the edge.
    - Configure WebSocket / SSE proxying for real-time A2UI streaming.
  - **Verification:** Penetration probe against public domain confirms write endpoints return 403 Forbidden.

---

## Phase 8: End-to-End Integration & Acceptance Verification

- [ ] **TASK-19: Comprehensive Acceptance Suite**
  - **Objective:** Create an end-to-end integration test (`tests/test_shadenet_acceptance.py`):
    - 1. Autonomous container boots up and discovers venues.
    - 2. Public user views calendar and zine (read-only).
    - 3. Steward generates address and completes mock ZKP 21+ attestation.
    - 4. Steward casts +1 vote on a 21+ show via A2A envelope $\rightarrow$ vote records.
    - 5. Steward attempts second vote $\rightarrow$ rejected with verbose explanation.
    - 6. Steward posts marketplace listing $\rightarrow$ appears on Serendipilyst board.
    - 7. Steward creates public Flag with skills tags $\rightarrow$ discoverable via tag query.
  - **Verification:** All acceptance tests pass with 100% exit code 0.
