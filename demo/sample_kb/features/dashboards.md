# Dashboards

Dashboards are configurable views of cross-project data. Available on Starter and above.

## Creating a dashboard

From the sidebar, click **+ → Dashboard**. Give it a name and pick a layout (1, 2, or 3 columns). Then drag widgets in from the right-hand panel.

## Available widgets

- **Burndown chart** — for a specific sprint.
- **Task count by status** — pie or bar.
- **Cycle time** — average time from In Progress to Done over a chosen window.
- **Throughput** — tasks completed per week.
- **At-risk tasks** — list, filterable by project.
- **Custom query** — paste a CQL (Cumulus Query Language) expression.

## Sharing

Dashboards can be private (visible only to you), team-visible (anyone in the project), or public (read-only link, no Cumulus account required). Public dashboards are useful for stakeholder updates but should not contain sensitive data — the link is unguessable but not password-protected.

## Refresh frequency

Dashboard widgets refresh every 5 minutes by default. You can force a refresh with the icon in the top-right of each widget. Custom query widgets refresh on page load only, to limit database load.

## Limits

Workspaces can have up to 50 dashboards on Business, 200 on Enterprise. Each dashboard supports up to 20 widgets.
