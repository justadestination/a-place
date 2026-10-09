# NightCal system maps (draft — task 7.4)

High-level maps. Detailed per-component diagrams get generated from the repo
once Batch D lands; these are the shapes the docs and onboarding will teach.

## 1. Event pipeline

```
Venue sites / FB / IG / venue-submitted
        │  (agent files event.create via agent pipeline — no scraping)
        ▼
Calendar API  →  shadenet.db (Spots, Spaces, Listed)
        │
        ▼
NightCal web: today timeline (hero) + hub modules
  hero  = chronological "road into the distance" (position = start time,
          billboard size = Bodies attendance gauge)
  slots = zine Expression · daily summary (generated from Spots) ·
          Box snapshot · Serendipilyst aggregator
```

Filters (tags, Spaces) are URL parameters — every view is shareable and
independently frameable. Works 2D now, hooks for 3D/AR later.

## 2. Identity & access

```
User ── Steward credential (bearer token, sole key to username + Box)
  │
  ├─ off-device encrypted backup at onboarding (per 0.9 tiered policy)
  ├─ lost phone → Steward restore from backup (4.2)
  └─ compromise → credential rotation (4.3)

Tiers: regular accounts throwaway (Thoughts/Exposures self-destruct in days);
Operator + Space/Listed accounts are the crown jewels.
```

No passwords anywhere. No password reset exists.

## 3. Bodies voting

```
User tells Steward "I'm going / not going" (user approval required)
        │
        ▼
Steward casts +/− through its agent identity
  (one agent per device identifier, registry; rate limits)
        │
        ▼
Tally → billboard sizing curve (0.5, the operator signs off on mock)
```

Threat model: casual abuse only (self-boost, rival-tank). Burst of fresh-agent
−s on one Spot → operator review. Device identifiers disclosed in the privacy
policy (8.1).

## 4. Zine graph (Umwelt Horizons)

```
Obsidian vault: markdown + frontmatter, [[links]] (git)
        │  (3.1 intake pipeline)
        ▼
Graph nodes (Expressions) + edges (3.3)
        │
        ├─ node pages (3.4)
        └─ Obsidian-style graph explorer (3.5)

Paper → screen: QR/mosaic print markers as AR portals (3.7, 3.8),
plain-URL fallback, print-survivability tested.
```

Seed personalities (3.6, the operator's writing): house voices modeling etiquette,
each piece carrying the disclosure cipher per 0.7.

## 5. Data & deploy (test build)

```
the primary host ← shady.example.org (public once built)
SQLite (shadenet.db) · CI/CD (6.6) · backups (6.4) · health checks (6.8)
Future: own server, then on-site downtown. Santa Rosa only.
```
