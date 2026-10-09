# Architecture Specification: 21+ Zero-Knowledge Proof (ZKP) Age Gate & mDL Selective Disclosure

## 1. Principles & Objectives

NightCal / ShadeNet operates under a strict dual-mode privacy model:
1. **Public Web is Read-Only**: Anonymous patrons can browse the calendar, read the zine, navigate the 3D map, and view event listings without any authentication, tracking cookies, or age gating.
2. **Mutating Writes Require 21+ Verification**: All write actions (submitting articles for intake, posting venue quick-edits, operator actions, and comments) require verifiable proof that the user is 21 years of age or older.
3. **Zero Knowledge / Zero Data Retention**: Verification proves only the mathematical predicate $\text{age} \ge 21$. The platform never collects, transmits, or stores legal names, birthdates, street addresses, or driver's license numbers.

---

## 2. Cryptographic Protocol: ISO/IEC 18013-5 Selective Disclosure

ShadeNet leverages mobile Driver's License (mDL) selective disclosure protocols based on ISO/IEC 18013-5:

```
[ Client Browser ]                 [ NightCal Server ]                 [ Issuing Authority (mDL) ]
        |                                   |                                     |
        | --- 1. GET /api/auth/zkp/challenge >|                                   |
        | <-- 2. Nonce + Predicate ("age >= 21")                              |
        |                                   |                                     |
        | --- 3. Request selective disclosure presentation ----------------------> |
        | <-- 4. mDL presentation token (Predicate: TRUE, Sig: DMV) <------------ |
        |                                   |                                     |
        | --- 5. POST /api/auth/zkp/verify ->|                                    |
        |       { challenge, claim, proof } | [ Verify signature & nonce ]        |
        | <-- 6. Signed 24-hr X-ZKP-Token --|                                     |
```

### 2.1 Challenge-Response
To prevent replay of captured presentations, each verification begins with a cryptographic challenge:
- Nonce: 16 cryptographically secure random bytes (32 hex characters).
- TTL: 300 seconds (5 minutes).
- Bound to client session if authenticated.

### 2.2 Token Issuance & Verification
Upon verifying the presentation:
- Server creates an HMAC-SHA256 signed age token.
- Token format: `<hex-encoded-json-payload>.<hmac-sha256-signature>`.
- Lifetime: 24 hours (`exp = now + 86400`).
- Validated on write endpoints via `X-ZKP-Token` header.

---

## 3. Server Enforcement & Abuse Defenses

| Action | Gate Behavior | Status Code |
| :--- | :--- | :--- |
| **Browsing listings / zine** | No gate prompt; public read-only access | `200 OK` |
| **Write attempt without token** | Blocked; returns new challenge | `403 Forbidden` (`gate_required: true`) |
| **Write with expired / forged token** | Blocked; security event logged | `403 Forbidden` |
| **Write with valid signed token** | Verified; allowed to execute | `200 OK` |

---

## 4. Front-End UX Architecture (`web/components/zkp-gate/`)

The gate dialog is rendered when a user attempts a write action or requests age verification:
- **Plain-Language Privacy Explainer**: Explicitly reassures the user that their identity remains pseudonymous.
- **Accessible Modal**: WCAG 2.2 AA compliant, strict design tokens (`var(--nc-*)`), full keyboard trapping and focus restoration.
- **Seamless Token Caching**: Upon successful verification, the token is held in `sessionStorage` and automatically attached as `X-ZKP-Token` to subsequent write calls.
