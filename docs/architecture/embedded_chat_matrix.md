# Embedded Matrix Chat Engine & Built-In Server (Task 5.1)

## Overview

NightCal carries its own **built-in, self-contained Matrix-compatible chat server** backed by SQLite (`shadenet.db`). This eliminates external dependencies, fragile SSO configurations, or link-outs to third-party services, while retaining protocol compatibility with Matrix Client-Server v3 API and providing optional bridge hooks to `chat.example.org`.

## Key Capabilities

1. **Zero-Step Transparent Authentication**:
   - When a patron opens the chat node (at `/chat/` or via embed `/embed/chat/`), the system authenticates the user in under 2 seconds.
   - Derives a deterministic cryptographic pseudonym:
     ```
     pseudonym = @anon-<sha256(user_id + salt)[:8]>:shady.example.org
     ```
   - No Matrix login screen or credential prompt ever appears.
   - The user↔pseudonym mapping is maintained strictly server-side in `chat_pseudonyms`; users cannot correlate another chatter's pseudonym to a platform username.

2. **Room Topology**:
   - **Town-Wide Domain General**: `#downtown-general:shady.example.org` (id `!general:shady.example.org`).
   - **Venue/Space Rooms**: One dedicated room per active venue (e.g. `#echo-music-hall`, `#mystic-theatre`), seeded automatically from the `venues` registry.

3. **Steward In-Room Assistant**:
   - The `@steward:shady.example.org` agent is present in all rooms.
   - Detects patron queries (e.g., *"@steward what's on tonight?"*, *"who's playing tonight?"*).
   - Dynamically inspects the live event calendar (`Spots`) and posts an immediate response with showtimes, lineups, and venue links.

4. **Operator Moderation**:
   - Operators can redact abusive or offensive messages (`POST /api/chat/moderate` with `op="redact"`).
   - Disruptive pseudonyms can be banned (`op="ban"`), preventing further message submission.

5. **Matrix Protocol Compatibility**:
   - Native support for standard Matrix Client-Server v3 endpoints:
     - `GET /_matrix/client/versions`
     - `GET /_matrix/client/v3/publicRooms`
     - `GET /_matrix/client/v3/rooms/{roomId}/messages`
     - `POST /_matrix/client/v3/rooms/{roomId}/send/m.room.message/{txnId}`
     - `GET /_matrix/client/v3/sync`
   - External bridge badge linking patrons to `chat.example.org` if they use an external Matrix/Element client.

6. **Patron Privacy Contract**:
   - Notice displayed prominently in the UI and documented in privacy policy (Task 8.1):
     *Room messages are public to all patrons and persist in room history (unlike ephemeral in-box Thoughts which self-destruct).*

## Touch Target & Accessibility Compliance
- All room buttons, composer inputs, and send buttons adhere to WCAG 2.2 AA target size (≥ 44px).
- Strict design tokens (0 raw hex colors, 0 raw px units).
