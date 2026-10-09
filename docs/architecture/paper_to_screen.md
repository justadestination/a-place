# Paper-to-Screen Interaction Flow Specification (Task 3.7)

## Overview
The printed NightCal zine pages act as physical portals. Pointing a smartphone camera at designated print elements (articles, venue profiles, QR/mosaic markers) bridges the physical print into interactive AR/digital layers.

This document defines the interaction flow, capability negotiation, and strict graceful degradation ensuring devices without AR capabilities receive a rich, responsive experience with zero dead ends.

---

## 1. Interaction Flow

```
[Physical Zine Page]
       │
       ▼ (Scan QR / Mosaic marker with iOS Camera or Android Lens)
[Scan Event: URL Launch]
  URL: https://shady.example.org/portal/?target=<id>&ar=1
       │
       ▼
[Portal Resolver (/portal/)]
       │
  ┌────┴─────────────────────────────┐
  │ Capability Probe (WebGL / WebXR) │
  └────┬─────────────────────────────┘
       │
 ┌─────┴─────────────────────────────────────┐
 │                                           │
 ▼ (WebXR immersive-ar supported)            ▼ (No WebXR / Desktop / iOS Safari non-XR)
[Interactive AR Spatial Portal]             [Accessible Digital Reader Fallback]
• 3D spatial node anchor                    • Complete formatted article & review prose
• Projected attendance billboard            • Author, tags, date, and verified citations
• Live tallies & attendance gauge           • Direct links to calendar & interactive zine map
• Spatial comment / letter layer            • Zero modal traps; instant first paint
```

---

## 2. Device Capability Negotiation

### Tier 1: Full WebXR AR (e.g. Chrome on Android, XR Headsets)
- `navigator.xr.isSessionSupported('immersive-ar')` resolves `true`.
- Renders 3D anchor and offers "Place in Room (AR)" camera overlay.
- Visual elements float in real-world scale anchored to the page.

### Tier 2: WebGL 3D Preview (e.g. Modern Desktop, iOS Safari)
- WebGL available, WebXR AR unavailable or permission denied.
- Provides interactive 3D orbit viewer with pan, zoom, and touch rotation.

### Tier 3: Accessible Fallback (No WebGL / Screen Reader / Low Power Mode)
- Full progressive enhancement:
  - Clean semantic HTML `<article>` with design tokens.
  - Resolves `target` (node ID, venue ID, or event ID).
  - Shows linked entities (e.g. venue address, showtimes).
  - Displays attendance gauges and direct navigation links.
  - Works completely without JavaScript execution (SSR/pre-rendered compatible).

---

## 3. URL Schema & Routing

- `/portal/?target=note:<slug>`: Opens zine note (article, review, editorial).
- `/portal/?target=event:<id>`: Opens specific event card and timeline.
- `/portal/?target=venue:<id>`: Opens venue profile and upcoming nights.
- `/portal/`: With no target, presents the portal index and camera scanner prompt.
