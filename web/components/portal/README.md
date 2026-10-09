# Paper-to-Screen Portal Component

Portal interface connecting printed zine scan markers into digital & AR content (Task 3.7).

## Purpose
Provides a responsive, accessible interface that resolves scanned physical print tokens into corresponding zine dispatches, reviews, and events.

## Features
- **Capability Negotiation**: Probes device support for WebGL and WebXR (`immersive-ar`).
- **AR Activation**: Where supported, launches spatial camera overlay and interactive anchors.
- **Graceful Fallback**: On devices without AR capabilities (or where permissions are denied), cleanly presents the complete article prose, meta information, and direct calendar/node-map links.
- **Zero Dead Ends**: Eliminates modal traps and broken states for non-AR users.
