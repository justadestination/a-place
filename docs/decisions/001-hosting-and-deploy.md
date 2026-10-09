# Decision 001: Hosting & Deploy Target

- **Date:** 2026-10-08
- **Decider:** the operator
- **Status:** Approved

## Decision

1. **Target Host:** the server currently associated with `shady.example.org`.
2. **Current Role:** Active test environment for the integrated ShadeNet / NightCal build.
3. **Future Progression:**
   - Step 1: the server test deployment (`shady.example.org`).
   - Step 2: Migration to a dedicated standalone server.
   - Step 3: Migration to physical on-site hosting downtown (Santa Rosa).
4. **Deploy Topology:**
   - Web frontend static assets served directly via Caddy from `web/`.
   - `/api/*` requests reverse-proxied to NightCal Python daemon listening on `127.0.0.1:8765`.
   - Public URL: `https://shady.example.org`.
