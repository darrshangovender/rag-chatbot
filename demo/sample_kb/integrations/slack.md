# Slack Integration

Connect Cumulus to Slack for notifications, task creation, and link previews.

## Installation

A workspace admin clicks **Settings → Integrations → Slack → Connect**, then authorises the Cumulus app in Slack. The Cumulus bot joins the workspace as `@cumulus`.

## Per-user authorisation

After the workspace is connected, each Cumulus user runs `/cumulus connect` in any Slack channel to link their Cumulus account to their Slack identity. Without this step, notifications won't reach them and `/cumulus` slash commands will fail.

## Slash commands

- `/cumulus create <project> <title>` — creates a task in the named project, assigned to you.
- `/cumulus search <query>` — returns the top 5 matching tasks as a Slack message with deep links.
- `/cumulus today` — lists your tasks due today.
- `/cumulus mute` — pauses all Slack notifications for 2 hours.

## Link previews

Paste a Cumulus task or project URL into Slack and the bot will unfurl it into a card showing title, status, assignee, and a "View in Cumulus" button. Unfurls respect your Slack workspace's privacy settings — private channels still get full unfurls, but only members with access to the task can view the underlying page.

## Disconnecting

Per-user: run `/cumulus disconnect`. Workspace-wide: **Settings → Integrations → Slack → Disconnect**. Disconnecting at the workspace level revokes the bot's access immediately for all users.
