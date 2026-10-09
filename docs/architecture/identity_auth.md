# Identity, Authentication & Passkeys Architecture (Task 4.1)

## Overview

NightCal identity architecture implements **Passkeys (WebAuthn / FIDO2)** as the primary, phishing-resistant authentication mechanism for human users and Steward operators, alongside a secure **Username Fallback** option.

---

## 1. Authentication Primitives

### Primary: Passkeys (WebAuthn / FIDO2)
- **Ceremony**:
  1. Client requests challenge: `GET /api/auth/register/options?username=<user>`
  2. Server generates a cryptographically random 32-byte challenge with a 300s TTL.
  3. Client invokes `navigator.credentials.create()` with biometric / platform authenticator (TouchID, FaceID, Windows Hello, YubiKey).
  4. Client sends attestation to `POST /api/auth/register/verify`.
  5. Server stores credential record (`credential_id`, `public_key`, `sign_count`) and mints an active session token.
- **Login**:
  1. `GET /api/auth/login/options` -> retrieves challenge + allowed credentials list.
  2. `navigator.credentials.get()` -> returns assertion.
  3. `POST /api/auth/login/verify` -> verifies challenge, increments sign count, mints session.

### Secondary: Username Fallback
- For devices or legacy browsers without platform WebAuthn support.
- Passwords are never stored in plaintext. They are salted with 16 cryptographically random bytes and hashed with `PBKDF2-HMAC-SHA256` (100,000 iterations).

---

## 2. Session Management

- Sessions are identified by random 256-bit URL-safe tokens (`sess_...`).
- Stored in SQLite `sessions` table with created timestamp, expiration timestamp (default 7 days), device description, and revocation timestamp.
- **Revocation**: Calling `POST /api/auth/logout` sets `revoked_at = now()`, immediately invalidating all subsequent requests with that bearer token.

---

## 3. Database Schema

```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    steward_id TEXT,
    salt TEXT,
    password_hash TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE passkeys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    credential_id TEXT UNIQUE NOT NULL,
    public_key TEXT NOT NULL,
    sign_count INTEGER NOT NULL DEFAULT 0,
    transports TEXT,
    nickname TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    device_info TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
```

---

## 4. Front-End Component & Embed Routes

- Component: `web/components/auth-dialog/`
- Full-page route: `/auth/`
- Embed route: `/embed/auth-dialog/` (and `/embed/auth/`)
- Adheres strictly to design token discipline (zero raw hex or px) and passes WCAG 2.2 AA accessibility audits with 0 violations.
