# Account Deletion and Data Export Architecture

**Status:** Completed & Verified (Task 4.5)  
**Compliance Standards:** GDPR (Articles 15 & 17), CCPA (Civil Code § 1798.100 & § 1798.105)

---

## 1. Overview & Policy Decisions

NightCal provides self-service user controls for personal data portability and account erasure:

1. **Right of Access / Portability (GDPR Art. 15 / CCPA § 1798.100):**
   - Users may export a machine-readable JSON archive containing their entire profile, passkey metadata, session history, saved bookmarks/earmarks, preferences, and voting history.
   - Cryptographic secrets (salts, password hashes) are strictly excluded from the exported archive.

2. **Right to Erasure / "To Be Forgotten" (GDPR Art. 17 / CCPA § 1798.105):**
   - Users may initiate irreversible deletion of their account.
   - To guard against accidental loss, users must pass a confirmation challenge: typing their exact username and checking an explicit acknowledgment checkbox.
   - **Zero Residual Rows Guarantee:**
     - User credentials (`users`), passkeys (`passkeys`), active and expired sessions (`sessions`), recovery codes (`recovery_codes`), active challenges (`auth_challenges`), preferences (`user_preferences`), and bookmarks (`user_earmarks`) are immediately hard-deleted from SQLite store.
     - User-specific tallies and votes (`nightcal_tallies` where `steward_id = user.steward_id` or `steward_id = user.id`) are purged or anonymized to ensure zero linkability to the former user.

---

## 2. API Endpoints

### 2.1 GET `/api/auth/export`
- **Authentication:** Required (Bearer token, `X-Session-Token`, or `?session=...`)
- **Headers:** `Content-Disposition: attachment; filename="nightcal-export-{username}.json"`
- **Response Format:**
```json
{
  "format_version": "1.0",
  "compliance": "GDPR/CCPA Article 15 (Right of Access)",
  "exported_at": "2026-10-09T08:30:00-07:00",
  "user": {
    "id": "usr_...",
    "username": "solaris",
    "display_name": "Solaris Dawn",
    "steward_id": "steward_solaris_77",
    "created_at": "..."
  },
  "passkeys": [...],
  "sessions": [...],
  "preferences": {...},
  "earmarks": [...],
  "votes": [...],
  "escalations": [...]
}
```

### 2.2 DELETE `/api/auth/account` (or POST `/api/auth/account/delete`)
- **Authentication:** Required (Bearer token, `X-Session-Token`, or `?session=...`)
- **Request Body:**
```json
{
  "confirmUsername": "solaris"
}
```
- **Response Format:**
```json
{
  "success": true,
  "deleted_user_id": "usr_...",
  "username": "solaris",
  "deleted_at": "2026-10-09T08:30:00-07:00"
}
```

---

## 3. UI Component (`account-settings`)

Located at `web/components/account-settings/` with route `/embed/account-settings/`:
- Fully responsive across phone, tablet, and desktop viewports.
- WCAG 2.2 AA compliant with zero Axe violations.
- Interactive controls meet the minimum target size of 44px (`min-height: var(--nc-size-target)`).
- Zero raw hex colors or px units in CSS (100% design token discipline).
