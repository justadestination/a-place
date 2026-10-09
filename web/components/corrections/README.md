# Corrections and Forget UI

Zine contract corrections UI implementing append+outrank semantics and separate Forget policy control per Task 3.3.

## Semantics
- **Append + Outrank**: Submitting a correction appends to the immutable corrections ledger. In presentation, the correction outranks the original note text while preserving transparent history.
- **Forget Control**: Separate policy-compliant control that allows author/subject redaction requests under the ShadeNet data retention policy.
