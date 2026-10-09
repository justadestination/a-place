# Article Intake Component

Zine intake & instantiation interface (Task 3.5).

## Purpose
Provides a responsive, accessible interface for submitting drafts, filtering automated spam, reviewing submissions, and approving/instantiating articles directly into the vault and zine content graph.

## Features
- **Intake Form**: Fields for Title, Piece Type, Author/Steward URI, Associated Venues, Associated Events, and Markdown body with `[[wiki-links]]`.
- **Spam Moderation**: Client- and server-side heuristics flag spam, link stuffing, or abusive promotional patterns, giving instant plain-language reasons.
- **Review Queue**: Lists submissions by status (`pending`, `instantiated`, `rejected`).
- **One-click Review**: Operators can approve to instantiate as a graph node or reject with a custom plain-language reason.
- **A11y**: WCAG 2.2 AA compliant, minimum 44px tap targets, visible focus outlines, proper aria labels and alerts.
