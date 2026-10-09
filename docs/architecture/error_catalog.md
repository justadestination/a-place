# ShadeNet Error Catalog (Task 6.2)

Standardized catalog of plain-language user-facing errors across NightCal and ShadeNet services. Every error includes a plain-language explanation and a concrete recovery step. No raw stack traces or internal system paths are ever surfaced to users.

| Error Code | HTTP Status | Plain-Language Message | Recovery Action / Next Step | Help Link / Target |
|---|---|---|---|---|
| `ERR_NOT_FOUND` | 404 | "We couldn't find the page or event you requested." | "Check the date or return to tonight's listings on the calendar." | [`/`](file:///) |
| `ERR_BAD_REQUEST` | 400 | "The submitted data was incomplete or in an unexpected format." | "Verify the fields and try submitting again." | [`/api/docs`](file:///) |
| `ERR_METHOD_NOT_ALLOWED` | 405 | "This endpoint does not support that request method." | "Use GET for data or POST for actions per the API specification." | [`/api/docs`](file:///) |
| `ERR_UNAUTHORIZED` | 401 | "A valid steward or operator identity is required for this action." | "Ensure your steward credential is active and approved." | [`/system/`](file:///) |
| `ERR_RATE_LIMITED` | 429 | "Too many requests received from this identity." | "Please wait 60 seconds before casting further tallies or requests." | [`/`](file:///) |
| `ERR_UPSTREAM_UNAVAILABLE` | 502 | "The live venue feed or scraper did not answer." | "Cached listings remain active; retry refreshing in a few moments." | [`/`](file:///) |
| `ERR_INTERNAL_ERROR` | 500 | "Something unexpected happened behind the scenes." | "The incident was logged with your Trace ID. Refresh to try again." | [`/`](file:///) |

## Payload Schema

API errors are returned in a standard envelope:
```json
{
  "code": "ERR_NOT_FOUND",
  "error": "We couldn't find the page or event you requested.",
  "next_step": "Check the date or return to tonight's listings on the calendar.",
  "status_code": 404,
  "trace_id": "a1b2c3d4e5f67890",
  "help_url": "/"
}
```

## Security Invariants
- **No Stack Traces**: Python exceptions, tracebacks, and internal file paths are stripped before building the response.
- **Trace ID Correlation**: The `trace_id` in the user response matches the `request_failed` structured log in the operator log stream.
