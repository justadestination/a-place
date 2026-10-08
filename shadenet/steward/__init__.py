"""Steward - Personal Agent PWA with A2A address (shadenet.steward).

ZKP 21+ activation gate (Spec A):
- W3C Digital Credentials API navigator.identity.get() requesting
  age_over_21: true from mDL/wallets
- attestation token bound to Steward local a2a:// public key
- SHADENET_DEV_MODE=1 dev bypass for CI

Server side (Python):
- server.py             A2A ingress airlock + 21+ attestation check
- command_engine.py     abuse/rate-limit + attestation validation
- inboxes.py, personal_agent.py, venue_agent.py, public_board.py,
  subscriptions.py      A2A protocol + per-agent mailboxes

Client side (vanilla JS):
- steward.js            keygen, attestation binding, verbose gunode-primaryils,
                        adaptive filtering (localStorage/IndexedDB)
- manifest.webmanifest  installable PWA
- sw.js                 offline service worker
- index.html            Steward UI with settings view
"""
__all__ = [
    "command_engine", "inboxes", "personal_agent", "venue_agent",
    "public_board", "subscriptions", "mcp_server",
]
