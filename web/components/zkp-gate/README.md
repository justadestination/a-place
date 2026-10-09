# 21+ ZKP Age Gate Component

Privacy-preserving zero-knowledge proof age gate implementing mDL (ISO/IEC 18013-5) selective disclosure verification for community write operations.

## Capabilities
- **Read-Only Anonymous Browsing**: Unrestricted public access to all read paths.
- **Cryptographic Gate**: Intercepts mutating actions (article submissions, edits) requiring proof of age ≥ 21.
- **Selective Disclosure**: Zero personal data collection (no legal names, full birthdays, or addresses).
- **Session Caching**: Retains 24-hour cryptographic token in `sessionStorage` attached via `X-ZKP-Token`.
- **WCAG 2.2 AA Accessibility**: Full keyboard navigability, high contrast, ARIA live regions, and strict design token adherence.

## Usage
```javascript
import { zkpGateView } from "./zkp-gate.js";

const el = zkpGateView({
  onVerify: async ({ claim, status }) => { ... },
});
document.body.appendChild(el);
```
