# Lost-Phone Recovery Component

Accessible component for account credential recovery when an authenticator passkey device is lost or inaccessible.

## Capabilities
- **Self-Service Recovery**: Single-use salted PBKDF2 recovery code redemption without operator assistance.
- **Support Escalation Form**: Edge-case submission for users who lost both passkeys and recovery codes.
- **Passkey Re-enrollment Flow**: Immediately prompts enrollment of replacement credentials upon successful recovery.
- **Full WCAG 2.2 AA Accessibility**: Uses semantic markup, ARIA live region status messaging, focus indicators, and strict design token values.

## Usage
```javascript
import { recoveryView } from "./recovery.js";

const el = recoveryView({
  apiBase: "",
  onRecover: async ({ username, recoveryCode }) => { ... },
  onEscalate: async ({ username, contact, notes }) => { ... },
});
document.body.appendChild(el);
```
