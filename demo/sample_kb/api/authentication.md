# API Authentication

The Cumulus REST API uses bearer tokens. All requests must include an `Authorization: Bearer <token>` header.

## Personal access tokens

Generate a personal access token at **Settings → Developer → Tokens → New token**. Tokens inherit your user permissions — a token can do anything you can do in the UI, no more, no less. You can give a token a name and an optional expiry between 1 day and 1 year (or no expiry, but not recommended).

Tokens are shown once at creation. If you lose a token, revoke it and create a new one.

## OAuth 2.0

For multi-tenant apps that need to act on behalf of Cumulus users, register an OAuth client at **Settings → Developer → OAuth apps**. Cumulus supports the authorisation code flow with PKCE. Standard scopes:

- `read:tasks`
- `write:tasks`
- `read:projects`
- `write:projects`
- `read:workspace`
- `admin:workspace` (requires explicit approval per workspace)

## Token rotation

Personal access tokens with an expiry will trigger a reminder email 7 days before expiry. There is no automatic rotation — you must generate a new token and update your integration. The old token continues to work until its expiry.

## Revoking a token

Revoke at **Settings → Developer → Tokens**. Revocation takes effect within 60 seconds across our edge. Tokens are also auto-revoked when the owning user is removed from the workspace.
