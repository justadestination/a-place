# Account Settings & Lifecycle Component (`account-settings`)

Implements **Task 4.5: Account deletion + data export**.

## Features
- **GDPR Article 15 (Right of Access) & CCPA compliant personal data export**:
  - One-click machine-readable JSON download of account profile, passkeys, sessions, preferences, bookmarks/earmarks, and voting history.
  - Automatically scrubs cryptographic private material, password hashes, and salts.
- **GDPR Article 17 (Right to Erasure) compliant account deletion**:
  - Multi-factor deletion confirmation: required typing of exact username and confirmation checkbox.
  - Zero residual rows policy: purges user row, passkeys, sessions, recovery codes, challenges, preferences, and personal bookmarks.
  - Anonymizes or deletes voting history to guarantee user unlinkability.
- **Accessibility & Design Token Discipline**:
  - 100% WCAG 2.2 AA compliant with zero Axe violations.
  - Interactive touch targets >= 44px (`min-height: var(--nc-size-target)`).
  - Strictly 0 raw hex colors and 0 raw px units.
