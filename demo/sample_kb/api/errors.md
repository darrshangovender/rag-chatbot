# API Errors

The Cumulus API uses standard HTTP status codes and returns JSON error bodies.

## Error format

```json
{
  "error": {
    "code": "task_not_found",
    "message": "No task with id 'tsk_doesnotexist' in this workspace.",
    "request_id": "req_01H4QY..."
  }
}
```

Always log the `request_id` — support can look up the full request and response in our edge logs using this ID.

## Common error codes

- **400 invalid_request** — malformed JSON, missing required field, or unknown field. The `message` will name the field.
- **401 invalid_token** — bearer token is missing, malformed, or revoked.
- **403 insufficient_scope** — token is valid but doesn't have the scope required for this endpoint.
- **403 forbidden** — token is valid and scoped correctly, but the underlying user doesn't have permission on the resource.
- **404 not_found** — resource doesn't exist or isn't visible to the token holder. We don't distinguish "doesn't exist" from "no permission" — both return 404 to prevent enumeration.
- **409 conflict** — write conflicts with another concurrent write. Refetch and retry.
- **422 invalid_state** — request is well-formed but violates a workflow rule (e.g. invalid status transition).
- **429 rate_limited** — see API Rate Limits.
- **500 server_error** — our problem. Retry with backoff. If persistent, file a ticket with the `request_id`.
- **503 unavailable** — we're degraded. The `Retry-After` header tells you how long to wait.
