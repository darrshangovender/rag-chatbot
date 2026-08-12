# Webhooks

Cumulus can POST event payloads to your URL when things change in a workspace.

## Setup

Create a webhook at **Settings → Developer → Webhooks → New**. Provide an HTTPS URL and select the event types to subscribe to. Webhooks are scoped to either the whole workspace or a single project.

## Supported events

- `task.created`
- `task.updated` (any field change)
- `task.status_changed`
- `task.deleted`
- `comment.posted`
- `sprint.started`
- `sprint.closed`
- `member.added`
- `member.removed`

## Payload format

```json
{
  "id": "evt_01H...",
  "type": "task.status_changed",
  "workspace_id": "ws_abc",
  "occurred_at": "2026-06-24T10:15:23Z",
  "actor": { "id": "usr_xyz", "name": "Alex Chen" },
  "data": { "task": { "...": "..." }, "from": "In Progress", "to": "Done" }
}
```

## Signing

Every webhook request includes an `X-Cumulus-Signature` header containing an HMAC-SHA256 of the raw request body using the per-webhook secret. Verify the signature before processing.

## Retries

A non-2xx response triggers retries at 30s, 5m, 30m, 2h, and 12h. After 5 failures the webhook is automatically disabled and the workspace admin is notified by email. Re-enable from the webhook's settings page once you've fixed the receiver.

## Replay

For each webhook you can view the last 1,000 deliveries and re-send any of them manually — useful for testing after a fix.
