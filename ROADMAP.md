# Derivee Roadmap

Higher-order map of what we've built, where we are, and where we're heading.
Updated as the project evolves — this is the canonical "why are we doing this" doc.

---

## 1. Origin / Why

Derivee is a privacy-first autonomous agent scaffolding and cited local intelligence system.
The core concept marries three symbiotic layers:

1. **Autonomous Agent Scaffold (`agent-scaffold/`):** A dual-role agent (Builder + Researcher) that runs locally whenever possible, escalates to cloud only when reasoning depth demands it, and uses a self-hosted Synapse Matrix room (`matrix.example.org:8008`) as its secure rendezvous channel with a human.
2. **Cited City Database & Presentation (`towncrier/`):** A factual knowledge engine and night sheet for downtown Metropolis. One town, one person, cited primary sources (OpenStreetMap, venue sites, public calendars), immutable listings, anti-hallucination rules, and a 4-axis night calendar (`nightcal`).
3. **Decentralized Zine & Adaptive Surface (`zine/` & `avr_jit`):** An editorial publication pipeline compiling markdown notes with wikilinks into an AVR (Adaptive Viewport Resolution) node graph, accompanied by a JIT preference-adaptation engine spanning cross-device and AR/VR displays.

The scaffold is declarative — everything critical is YAML, code serves as the thin loader + MCP server + A2A protocol. The agent shares an intuitive lexicon with its human so communication stays low-signal.

---

## 2. Where we've come from (foundations & completed phases)

### 2.1 Agent scaffold (`agent-scaffold/`)

A working, coherent v1 skeleton:

- **Dual-role contracts** — Builder (`forge`/`polish`/`run_shell`) and Researcher (`scout`/`check`/`synthesize`). Each has a clear purpose, allowed tools, and constraints in `roles/`. Both share the lexicon and task list.
- **Declarative YAML config** — `agent.yaml` (roles, inference policy, escalation rules, rendezvous, persistence), `lexicon.yaml` (shared vocabulary), `tasks.yaml` (task schema + seed tasks), `mcp-tools.yaml` (5 declarative tool definitions), `matrix.yaml` (Synapse/Matrix config).
- **Real MCP server** — `mcp-server/server.py` is a runnable stdio server using `mcp` 2.x `MCPServer` with 5 `@mcp.tool()` handlers wired: `task_list`, `lexicon_lookup`, `matrix_signal`, `local_infer`, `run_shell`. Includes robust JSON-RPC stdout isolation and `logstack.py` error redaction.
- **Sandboxed execution** — `run_shell` has a cwd sandbox blocking directory escapes and temporary shared filesystems (`/tmp`, `/var/tmp`, `/dev/shm`).
- **Bootstrap** — `instantiate.sh` seeds `state/tasks.json` from `tasks.yaml` and handles environment initialization.
- **Seed tasks (T001–T004)** — Onboarding walk: confirm local Hermes endpoint, stand up MCP server, post Matrix handshake, expand lexicon.
- **Inference policy** — Local-first (Ollama at `127.0.0.1:11434`, model `hermes-3-llama-3.1-8b`), cloud fallback (OpenAI `gpt-4o`) only under escalation rules.

### 2.2 Towncrier & NightCal (`towncrier/`)

- **The Oak (Factual Store)** — Metropolis trunk; venues as branches; performers as leaves; shows as acorns inferred by clustering listings (`towncrier/resolve.py`). Every publishable fact requires an immutable citation URL (`entities.py` raises `UncitedFact` otherwise).
- **Overpass Discovery** — Queries OpenStreetMap Overpass API for venues within the downtown bounding box (`towncrier/discover.py`).
- **The Night Sheet (`nightcal/`)** — 4-axis responsive calendar UI (`static/index.html`) visualizing start hour (X), show lanes by venue (Y), community vote tallies (Z-depth), and set duration (wire). Serves A2UI v0.9 streaming protocol (`surface.py`).
- **Deployment** — Live daemon `nightcal.service` running on port 8765, reverse-proxied via Caddy across the Nebula mesh (`10.0.0.6`) and public gateway (`nightcal.example.org`).

### 2.3 Scaffold reviewer (`scaffold-reviewer/`)

A Hermes skill for reviewing small scaffolded codebases — especially YAML-heavy agent/MCP/declarative ones. Produces a structured report: snapshot, prioritized flags with file references, ordered build path, and reference documentation (`references/mcp-python.md`, `references/common-gotchas.md`, `scripts/inventory.py`).

### 2.4 Phase 1 Completed Milestones (commit `a93bbe5`)

1. **Per-Agent Inboxes & A2A Protocol:**
   - Implemented `command_engine.py` (JSON-RPC 2.0 command dispatching and schema validation).
   - Created `inboxes.py` (per-agent file-backed mailboxes in `state/inboxes/{agent_id}/inbox.jsonl`, store-and-forward semantics).
   - Built role agents: `personal_agent.py` (user agent), `venue_agent.py` (venue calendar agent), `public_board.py` (broadcast discovery), and `subscriptions.py` (pub/sub registry).
   - Verified end-to-end via `phase0_acceptance.py` (10/10 acceptance tests passing).
2. **NightCal Hardened:**
   - Added `social_hardened.py` to rigorously verify social and venue calendar sources against hallucinated listings.
3. **Entity Pages & Agent Cards Generators:**
   - `entity_pages.py`: Generates static HTML dossier pages for all 50 cited venues from `shadenet.db`.
   - `agent_cards.py`: Renders HTML cards for registered system agents and subscription surfaces.
4. **Zine Content Modules Pipeline [Spec §9 p.13]:**
   - Implemented `zine_pipeline.py`: 6-stage compiler reading Markdown vault pieces (`towncrier/zine/vault/`), validating YAML frontmatter, resolving `[[wikilinks]]` and IDs into graph edges, emitting `nodes.json` and `edges.json`, and generating the `avr_graph.json` payload.
   - Built-in link validator enforces Spec §9: broken wikilinks fail preview builds and block publication builds.
5. **AVR+JIT Adaptive Layer:**
   - Implemented `avr_jit.py`: Standardizes 4 shared layout keys (`textSize`, `density`, `eventSelection`, `colors`) across all presentation surfaces (NightCal, entity pages, boards, agent cards, AR portal, zine entry).

---

## 3. Where we are now

| Area | State |
|------|-------|
| Config YAML | Complete and internally consistent |
| MCP server | Real, runnable, 5 tools wired (`task_list`, `lexicon_lookup`, `matrix_signal`, `local_infer`, `run_shell`) |
| Roles | Written, constraints clear (Builder, Researcher, Personal, Venue, Board) |
| Lexicon | Complete v1 shared vocabulary in `config/lexicon.yaml` |
| Tasks | Schema + 4 seed tasks; runtime state in `state/tasks.json` |
| Tests | **100% Green across all suites**: 58 scaffold tests, 6 MCP protocol tests, 10 A2A acceptance tests, 467 Towncrier tests |
| Matrix | **Connected & Verified** — Synapse at `http://matrix.example.org:8008`, room `!rendezvous:matrix.example.org` ('Hermes'), live send verified |
| A2A / Mailbox | **Completed & Verified** — Per-agent inboxes, pub/sub subscription engine, JSON-RPC 2.0 command engine |
| Webserver / NightCal | **Active & Running** — `nightcal.service` running on port 8765, serving 4-axis night sheet and A2UI streaming API |
| Factual Database | **Operational** — SQLite `shadenet.db` with 50 entities, 53 listings, 54 clustered events, sample vote tallies |
| Zine Pipeline | **Operational** — 6-stage compiler, vault markdown parser, AVR node graph generator, wikilink validator |
| AVR+JIT | **Operational** — Cross-surface adaptive layout & user preference engine |
| Local inference | Endpoint + model configured (`hermes-3-llama-3.1-8b` on Ollama) |
| Cloud fallback | Escalation rules configured with secure env key retrieval (`CLOUD_API_KEY`) |

---

## 4. Where we're heading (Phase 2)

### 4.1 Immediate (v1.2 — hardening & live synchronization)

1. **Service Sync:** Reconcile production deployment between `/opt/shadenet/towncrier` and `/home/operator/Downloads/Derivee/towncrier` to ensure running `nightcal.service` serves the latest Phase 1 additions (entity pages, agent cards, hardened social parser).
2. **Matrix Rendezvous Loop:** Implement the background check loop declared in `agent.yaml` to allow ongoing autonomous monitoring and human check-in alerts via Matrix.
3. **Nebula Multi-Node A2A:** Extend the local file-backed mailbox into cross-host A2A messaging across Nebula mesh nodes (`fly`, `node-inference`, `node-primary`, `node-gateway`).

### 4.2 Near-term (v2 — real-world gates & zine release)

1. **Zine Real-World Publication Gates:** Implement the printing and distribution workflow (Spec §9: physical print layout export, PDF imposition).
2. **Venue Self-Hosting:** Lightweight client allowing participating venues to run their own local citation endpoints or export verified calendar feeds.
3. **Decentralized Vote Sync:** Cryptographically sign and sync local sample votes across community nodes without central authority.

### 4.3 Long-term (ecosystem evolution)

- **Autonomous Agent Fanout:** Multi-agent collaboration where Researcher scouts new events across town and Builder updates schemas and publishes zine reviews autonomously under human rendezvous review.
- **AR/VR Spatial Portal:** Full WebXR / AVR spatial visualization of the downtown night sheet and zine node graph in 3D.

---

## 5. Principles

1. **Local first, cloud only when needed.** Inference, tool execution, and state all prefer the local machine.
2. **Declarative over imperative.** YAML is the source of truth; code is the thin loader.
3. **Shared lexicon, low-signal communication.** The agent and human speak the same small vocabulary.
4. **Task list is the single source of truth.** The agent checks it before acting; nothing important happens off-task without a task being created.
5. **Matrix is the rendezvous, not the only channel.** It's the secure chat point; other channels (A2A mailbox, webserver) are additive and optional.
6. **No hardcoded secrets.** API keys, tokens, and credentials come from env or explicit config — never committed.
7. **No uncited facts.** Every published item requires an immutable public source URL. Contradictions are preserved as separate records.
