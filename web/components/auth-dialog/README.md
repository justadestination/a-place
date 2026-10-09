# Auth Dialog (`auth-dialog`)

Component implementing user identity, passkey creation, and login (Task 4.1).

- **Primary mechanism**: Passkeys (`PublicKeyCredential` / WebAuthn / FIDO2).
- **Secondary fallback**: Salted PBKDF2 username fallback.
- **Session management**: Cryptographic bearer token with storage sync and logout revocation.
- **Accessibility**: Full WCAG 2.2 AA compliant, labeled fields, visible focus states, zero raw hex tokens.
