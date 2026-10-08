# Shadenet Architecture Specification & Master Plan
**"A place in the Shade"**

Canonical specification for Shadenet, detailing system taxonomy, core modules, Steward (Personal Agent) capabilities, ZKP 21+ gate, multi-node hosting, phased todo-list, and the worker implementation prompt.

---

## 1. System Taxonomy & Overview

Shadenet is an autonomous, privacy-first, decentralized cited intelligence and night culture network.

```
┌────────────────────────────────────────────────────────────────────────┐
│                              SHADENET                                  │
├────────────────────────────────────────────────────────────────────────┤
│  ABOVE SEA LEVEL (Public Read Surfaces):                               │
│    - NightCal         ──► 4-Axis Responsive Night Calendar             │
│    - Umwelt Horizon   ──► Zine (Editorial, Reviews & Syndication)      │
├────────────────────────────────────────────────────────────────────────┤
│  THE GATES:                                                            │
│    - Steward          ──► The Personal Agent (PWA Client on Phone)     │
│                           with A2A Mailbox, Local Calendar, JIT & ZKP  │
├────────────────────────────────────────────────────────────────────────┤
│  BELOW SEA LEVEL (Engines, Marketplace & Mesh):                        │
│    - Serendipilyst    ──► Marketplace (Services, Board Posts, Gigs)    │
│    - Rooms            ──► Hosts & Venues (OSM-cited entities)          │
│    - Flags            ──► Public Agent Cards & Venue Dossiers          │
│    - Tri-Sync Mesh    ──► Hetzner VPS ◄► Cloudflare ◄► Tor ◄► Local Pi │
└────────────────────────────────────────────────────────────────────────┘
```

### Module Definitions
- **NightCal (The Calendar):** Public-facing 4-axis night sheet for regional shows (X: start hour, Y: venue lanes, Z: community sample tallies, Wire: set duration).
- **Umwelt Horizon (The Zine):** Decentralized editorial publication and news syndication compiled from a git markdown vault into an Adaptive Viewport Resolution (AVR) node graph with wikilink validation.
- **Serendipilyst (The Marketplace):** Community bulletin board for services, gigs, and notices. Actions require an activated Steward.
- **Steward (The Personal Agent):** Client-side personal agent running as a PWA on the phone. Holds private calendar, personal availability, skills registry, JIT layout preferences, and content guardrails.
- **Rooms (Hosts & Venues):** Physical venues and gathering spaces discovered via OpenStreetMap Overpass and enriched with primary-source citations.
- **Flags (Public Cards & Dossiers):** Public profile cards for venues (Rooms) and users/service providers (Stewards).

---

## 2. Access Model & ZKP 21+ Gate

### A. Two-Tier Access
1. **Public Clearnet Web (100% Read-Only):**
   - Anyone visiting the site can view NightCal and read Umwelt Horizon.
   - Non-tracking client-side age advisory modal on first visit.
   - Direct web mutations (`/api/events`, unauthenticated votes) are blocked at the edge.
2. **Steward Gate (All Write Actions):**
   - To vote (`+1`/`-1`), submit zine articles, post to Serendipilyst, or message peers, the user must act through their **Steward**.
   - An active Steward requires a verified cryptographic **Zero-Knowledge 21+ Proof**.

### B. ZKP 21+ Activation Flow
1. **Onboarding:** On first PWA launch on mobile, the Steward generates a local `a2a://agent/personal_<uuid>` keypair in device storage.
2. **Verification via W3C Digital Credentials API (`navigator.identity.get()`):**
   - User verifies via mobile driver's license (mDL ISO 18013-5 / Apple Wallet / Google Wallet / state eID).
   - Phone uses local biometric auth (Face ID / Fingerprint) to request selective disclosure:
     $$\text{Disclosed Attribute: } \{\text{age\_over\_21}: \text{true}\}$$
   - **Zero Surveillance:** Name, birthdate, address, photo, and license number are never released or transmitted.
3. **Cryptographic Key Binding:**
   - The Steward binds the issuer signature to its local public key:
     $$\text{Attestation Token} = \text{Sign}_{\text{Issuer}}(\text{age\_over\_21} = \text{true}) \parallel \text{Sign}_{\text{Steward}}(\text{agent\_address})$$
   - Prevents token replay or transfer across devices.
4. **Dev / Mock Mode:** A testnet flag (`SHADENET_DEV_MODE=1`) issues test attestations for local development and CI testing.

---

## 3. Steward (Personal Agent) Detailed Specifications

### A. Public Flag (Agent Card)
- Optional public profile card ("MySpace page without the social network").
- Displays: user declarations, public PGP/A2A address, availability, skills tags.
- User controls linkage: can be completely pseudonymous or linked to real-world identity; can choose whether it is tied to past marketplace postings.

### B. Personal Calendar & "Available For" Skills Directory
- **Personal Calendar:** Manages local private events, pinned NightCal shows, and user availability intervals.
- **Availability Declaration:** Users can declare "Available Times" (e.g. `Weekends 17:00–21:00`).
- **Skills Registry:** Users tag services they can perform (e.g. `#plumber`, `#soundtech`, `#bartender`).
- **Peer Tag Search:** Users can ask their Steward: *"Find an available plumber this weekend"*, which queries peer Flags via tag matching without third-party ad profiling.

### C. Verbose Gunode-primaryils & Transparent Explainability
When an action is capped, delayed, or held, the Steward explains **why** conversationally:
- **2-Message Unreplied Rule:** Holds outbound messages if 2 consecutive messages were sent to a peer without a reply until the recipient responds.
- **Outbound Tone Review:** Holds messages containing abusive, aggressive, or bullying language and prompts the user to rephrase.
- **Vote Cap:** Enforces exactly one `+1` or `-1` per event per verified Steward address.
- **Marketplace Cooldown:** Enforces rate-limiting between new Serendipilyst listings.
- **Age Gate:** Explains why 21+ venue actions require 21+ attestation.

### D. Adaptive Filtering (Choice-Based Learning)
- Content warnings (mature language, sensitive subjects) prompt the user with persistent options:
  - `[View Once]`
  - `[Always allow from this sender]`
  - `[Always allow for this category]`
  - `[Always discard without prompting]`
- **Local Preference Memory:** Choices are saved on-device (`steward_rules` in `localStorage`), adapting future filtering automatically.
- Users can review, modify, or clear learned rules in settings.

### E. Expanded JIT Engine & Localization
- Extends beyond 4 CSS variables to full dynamic rendering: typography scale, density modes, high-contrast/dark/light themes, and multi-language localization dictionaries.

---

## 4. News Syndication in Umwelt Horizon
- Introduces `type: syndicated` in markdown frontmatter.
- For authorized local independent news partners.
- Renders entries with an "Independent Partner Syndication" badge, original author credits, and canonical source links.

---

## 5. Deployment & Multi-Node Infrastructure

### A. Autonomous Geographic Container
- Packaged as a single OCI/Docker container.
- Environment variables: `SHADENET_LAT`, `SHADENET_LON`, `SHADENET_RADIUS_KM`.
- On boot, dynamically computes bounding box, queries OpenStreetMap Overpass, scrapes regional calendars, and populates SQLite autonomously.

### B. Tri-Sync Multi-Node Architecture
- **Primary Node:** Hetzner Cloud VPS running behind Cloudflare CDN/WAF (clearnet front door).
- **Darknet Fallback:** Tor Hidden Service (`.onion`) on the VPS.
- **Hyper-Local Fallback:** Physical Raspberry Pi operating on the local mesh network.
- **State Sync:** Automatic background replication (`scripts/sync_mesh.py`) syncing SQLite changefeeds and git-tracked zine articles across all three nodes.

---

## 6. Master Phased Todo-List

### Phase 1: Structural Unification & Containerization
- [ ] **1.1 Directory & Module Unification:** Consolidate `towncrier`, `agent-scaffold`, and `zine` into a clean package under `shadenet/` (`shadenet.nightcal`, `shadenet.horizon`, `shadenet.serendipilyst`, `shadenet.steward`).
- [ ] **1.2 Dynamic Geographic Bootstrapping:** Update `discover.py` to accept dynamic `(lat, lon, radius_km)` parameters, computing the bounding box and initializing the database automatically.
- [ ] **1.3 Container Packaging:** Create a multi-stage `Dockerfile` and `docker-compose.yml` packaging Python 3, Caddy, Tor daemon, and SQLite into an autonomous standalone container.

### Phase 2: Steward Core, ZKP 21+ Gate & Verbose Adaptation
- [ ] **2.1 PWA Shell:** Implement `manifest.webmanifest`, app icons, and an offline Service Worker.
- [ ] **2.2 ZKP 21+ Activation Gate:**
  - Implement client-side `steward_verify.js` using the W3C Digital Credentials API for mDL selective disclosure (`age_over_21: true`).
  - Bind attestation token to the Steward's `a2a://` public key.
  - Provide a developer bypass flag (`SHADENET_DEV_MODE=1`) for local testing and CI.
- [ ] **2.3 Verbose Explanations Engine:**
  - Build explanation message generator into `steward.js` for all limit events (2-message unreplied rule, tone check pause, vote cap, cooldowns, age gate).
- [ ] **2.4 Adaptive Memory & Choice-Based Filtering:**
  - Implement local decision memory: consent modals offer *"Remember for this sender"* and *"Always apply to this category"*.
  - Store filtering rules in on-device storage. Automatically apply learned preferences to future incoming messages and feed items.
- [ ] **2.5 Personal Calendar & Tag Skills:** Implement personal calendar storage, availability time slots, and the `#tag` lookup engine for "Available For" service queries.

### Phase 3: Unified Multi-View UI (NightCal, Horizon, Serendipilyst, Flags)
- [ ] **3.1 Unified Interface Shell:** Expand `static/index.html` into a unified navigation shell for NightCal, Umwelt Horizon, Serendipilyst, and Flags.
- [ ] **3.2 Umwelt Horizon Syndication:** Add `type: syndicated` to `zine_pipeline.py` with custom independent partner attribution and external links.
- [ ] **3.3 Public Flags:** Implement public agent cards (bio, declarations, availability, optional link to real identity or anonymous).

### Phase 4: A2A Ingress Airlock & Multi-Node Sync
- [ ] **4.1 Gated Ingress Gateway:** Wire `server.py` and `command_engine.py` to reject any mutation unless accompanied by a verified 21+ cryptographic attestation token.
- [ ] **4.2 Tri-Sync Engine:** Implement state sync routines replicating SQLite updates and zine git commits across Hetzner, Tor, and the local Raspberry Pi.

---

## 7. Implementation Prompt for Local Worker Agent

```markdown
# TASK SPECIFICATION: Build and Package "Shadenet" (A place in the Shade)

You are an expert autonomous software engineer tasked with building, unifying, and containerizing "Shadenet" from the existing codebase at /home/operator/Downloads/Derivee/.

## 1. System Taxonomy & Core Concept
- NightCal: 4-axis night sheet for regional shows (public read).
- Umwelt Horizon: Decentralized zine compiled from markdown vault into an AVR node graph (public read, supports syndicated partner news).
- Serendipilyst: Community marketplace and bulletin board (gated write).
- Steward: Client-side Personal Agent running as a PWA on the phone with an A2A address (a2a://agent/personal_<uuid>), holding private calendar, availability slots, skills registry, verbose explainers, and adaptive filtering.
- Flags & Rooms: Public profile cards for agents/services (Flags) and venues/hosts (Rooms).
- Access Model: Web surface is 100% read-only. To obtain an active Steward and vote or submit to the marketplace/zine, the user MUST prove they are 21+ via a zero-knowledge attestation (mDL / W3C Digital Credentials).

## 2. Technical Requirements

### A. ZKP 21+ Activation Gate & Identity Binding
- In static/steward.js:
  - Integrate a 21+ verification flow using the W3C Digital Credentials API (navigator.identity.get() requesting age_over_21: true from mDL/wallets).
  - Bind the resulting signature to the Steward's local a2a:// public key.
  - Provide a developer bypass (SHADENET_DEV_MODE=1) that issues test attestations for automated testing and CI.
- In command_engine.py:
  - Verify that sender a2a:// addresses carry a valid, non-expired 21+ attestation before executing write actions (event.vote, board.post, event.create, zine.submit).

### B. Verbose Steward & Adaptive Choice-Based Filtering
- Verbose Explanations:
  - When an action is restricted (2-message unreplied rule, tone check pause, vote cap, marketplace cooldown, or 21+ gate), the Steward UI must display a clear, conversational explanation of the exact rule and how to proceed.
- Adaptive Decision Memory:
  - Inbound content warnings (mature language, sensitive topics) must include choice persistence options: "View Once", "Always allow from this sender", or "Always allow this category".
  - Persist choices in localStorage/IndexedDB. Automatically apply learned preferences to future incoming messages and feed items without re-prompting.
  - Provide a settings view allowing users to review and reset learned filtering rules.

### C. Packaging & Autonomous Discovery
- Create a multi-stage Dockerfile and docker-compose.yml running Python 3, Caddy, and Tor daemon.
- Dynamic geographic bootstrap: accept SHADENET_LAT, SHADENET_LON, and SHADENET_RADIUS_KM. If set, discover.py dynamically computes the bounding box, queries OSM Overpass, and populates the database automatically.

### D. Steward Phone Engine (PWA)
- Implement manifest.webmanifest and a service worker.
- Personal calendar with user availability times and tagged skills registry ("#plumber, weekends 5-9").
- Wrap all actions in A2A JSON-RPC envelopes dispatched to /api/a2a.

### E. Umwelt Horizon Syndication
- Update nightcal/zine_pipeline.py to support type: syndicated frontmatter.
- Render syndicated entries with partner news attribution badges and canonical links.

### F. Multi-Node Sync
- Provide scripts/sync_mesh.py to replicate SQLite changefeeds and zine commits between primary (Hetzner), darknet (Tor), and edge (Raspberry Pi) nodes.

## 3. Constraints
- Use Python 3.11+ and vanilla modern JavaScript (zero heavy JS frameworks).
- All existing tests in tests/ must continue to pass.
- Do not delete existing cited facts in data/shadenet.db.
- Verify every feature with unit and integration tests.
```
