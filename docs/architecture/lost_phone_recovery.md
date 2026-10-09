# Architecture Specification: Lost-Phone Recovery & Credential Restoration

## 1. Executive Summary

NightCal / ShadeNet accounts are secured primarily via hardware-backed WebAuthn passkeys. When an authenticator device (phone, laptop, security key) is lost, destroyed, or wiped, the user must be able to restore access securely without compromising the system's privacy-preserving, decentralized tenets.

This specification details:
1. **Self-Service Recovery**: Primary restoration mechanism requiring zero operator intervention using salted PBKDF2 single-use recovery codes.
2. **Support Escalation Path**: Fallback procedure for exceptional situations where all physical credentials and codes are lost.
3. **Cryptographic Protection & Abuse Mitigation**: Defense against brute-force guessing, username enumeration, and replay attacks.

---

## 2. Self-Service Recovery Flow

### 2.1 Code Generation & Ingestion
- At the time of account creation or passkey onboarding, the user is presented with a set of **8 cryptographically strong single-use recovery codes** (e.g., `NC-A1B2-C3D4`).
- **Storage Policy**:
  - The server **never** stores plaintext recovery codes.
  - Each code is individually hashed with a unique 16-byte random salt using PBKDF2-HMAC-SHA256 (100,000 iterations).
  - Stored in the SQLite `recovery_codes` table with `id`, `user_id`, `salt`, `code_hash`, `created_at`, and `consumed_at`.

### 2.2 Redemption & Device Re-enrollment
1. User navigates to `/auth/` and selects **"Lost Authenticator / Recover Account"** or accesses `/embed/recovery/`.
2. User provides their `username` and any unconsumed `recovery_code`.
3. The server locates the candidate user record, verifies the code against active unconsumed hashes, and atomically sets `consumed_at = CURRENT_TIMESTAMP`.
4. A high-privilege temporary recovery session is established for the user.
5. The client immediately prompts the user to enroll their new device passkey via WebAuthn registration.
6. Once the new passkey credential is saved in the database, the account is fully restored to standard passkey authentication.

---

## 3. Support Escalation Path

When a user has lost both their authenticator hardware and their stored recovery codes:

1. **Submission**: User submits an escalation request via `POST /api/auth/recovery/escalate` providing:
   - `username`
   - Secondary contact method (verified email, Signal, or out-of-band contact)
   - Identity verification context / notes (e.g., recent event submission details, steward fingerprint if known).
2. **Queueing**: The request enters the `recovery_escalations` table with status `pending`.
3. **Operator Console Review**:
   - Authorized operators review the request inside `/operator` under the **Content Moderation & Identity Escalation Queue**.
   - Operator initiates an out-of-band verification challenge.
   - Upon successful manual verification, the operator issues a single-use administrative reset token or generates a replacement recovery batch.
4. **Audit Trail**: Every escalation state change is permanently logged in the structured audit log.

---

## 4. Threat Model & Abuse Defenses

| Threat Vector | Mitigation Strategy |
| :--- | :--- |
| **Username-only probing** | Submitting a username without a valid recovery code returns generic `401 Unauthorized`. No hint is given regarding whether the username exists or whether codes remain. |
| **Brute-force attack** | Rate limited via global token-bucket (`shadenet/ratelimit.py`) on `/api/auth/recovery/*`. Repeated failures incur progressive exponential delays. |
| **Replay attack** | Atomic SQL update ensures a code cannot be redeemed more than once (`consumed_at IS NULL` guard). |
| **Side-channel timing attack** | PBKDF2 hash verification uses constant-time comparison `hmac.compare_digest`. |
