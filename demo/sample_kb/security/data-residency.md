# Data Residency

Enterprise customers can choose where workspace data is physically stored.

## Available regions

- **US** — Virginia (us-east-1, primary) and Oregon (us-west-2, DR replica).
- **EU** — Ireland (eu-west-1, primary) and Frankfurt (eu-central-1, DR replica).
- **AU** — Sydney (ap-southeast-2, primary) and Melbourne (ap-southeast-4, DR replica).

Each region is isolated — data, encryption keys, and search indices stay within the region. Cross-region access is only available to Cumulus engineers under break-glass procedures audited monthly.

## Choosing a region

Region is selected at workspace creation. Migrating an existing workspace between regions is possible but disruptive: it takes 24-72 hours, requires a maintenance window, and is offered once per workspace as part of an active Enterprise contract.

## What lives in-region

- All user-generated content (tasks, comments, attachments, custom fields).
- Search indices.
- Audit logs.
- Backups (encrypted, retained 35 days).

## What is global

- Account metadata for Cumulus authentication (email, hashed password, MFA secret).
- Billing records.
- The marketing website and the help centre.

If you have residency requirements that exclude any global storage, contact sales — we can configure an isolated identity layer for an additional fee.
