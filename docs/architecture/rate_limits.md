# ShadeNet Global Rate Limiting & Abuse Defense

## 1. Overview
Beyond tally vote rules, ShadeNet implements global rate limiting using a token bucket algorithm to protect public endpoints, submissions, and identity entrypoints against flooding and automated denial-of-service.

## 2. Default Rate Limits

| Category | Endpoints / Scope | Capacity (Burst) | Sustained Rate |
|---|---|---|---|
| `api` | `/api/model`, `/api/surface`, general reads | 60 requests | 1.0 req/sec |
| `submissions` | `/api/action` (votes), `/api/events` writes | 15 requests | 0.5 req/sec (1 per 2s) |
| `login` | Passkey authentication, session issuance | 5 requests | 0.1 req/sec (1 per 10s) |
| `operator` | `/api/operator/*` management endpoints | 1,000 requests | 100.0 req/sec |

## 3. Response Format & Headers
When a client exceeds the allocated bucket tokens, the server immediately returns **HTTP 429 Too Many Requests**:

### Headers
- `Retry-After`: integer number of seconds the client must wait before retrying.
- `Content-Type`: `application/json; charset=utf-8`

### Payload
```json
{
  "error": "Rate limit exceeded. Please back off.",
  "code": "ERR_RATE_LIMITED",
  "retry_after": 2,
  "next_step": "Wait 2 seconds before retrying this request."
}
```

## 4. Operator Overrides
Operators and authorized services can bypass rate limiting by supplying an authorized token or active cryptographic key in the request headers:
- `Authorization: Bearer <operator_token>`
- `X-Operator-Token: <token>`

Exempt tokens are registered via `limiter.add_operator_override(token)`.
