# API Rate Limits

Rate limits are per workspace, not per token. All tokens issued by users in a workspace share the same bucket.

## Limits by plan

- **Starter** — 60 requests per minute, 5,000 per day.
- **Business** — 600 requests per minute, 100,000 per day.
- **Enterprise** — 3,000 requests per minute, no daily cap; soft-throttle agreed in SLA.

The free plan does not include API access.

## Response headers

Every API response includes:

- `X-RateLimit-Limit` — the bucket size.
- `X-RateLimit-Remaining` — requests remaining in the current window.
- `X-RateLimit-Reset` — UNIX timestamp when the window resets.

When you exceed a limit, the API returns HTTP 429 with a `Retry-After` header indicating the number of seconds to wait.

## Best practices

- **Use ETags.** Read endpoints support conditional requests with `If-None-Match`. A 304 response does not count against your rate limit.
- **Use webhooks instead of polling.** If you're polling `GET /v1/tasks` for changes, switch to a `task.updated` webhook. We see ~95% lower request volume from teams that do this.
- **Batch writes.** The `POST /v1/tasks/batch` endpoint accepts up to 100 tasks per call and counts as a single rate-limit unit.

## Burst allowance

Each workspace has a 20% burst allowance on top of the per-minute limit, refilled at the start of every minute. A 600 RPM limit accepts up to 720 requests in a single second-long burst, then enforces the per-minute average.
