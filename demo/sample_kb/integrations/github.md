# GitHub Integration

The GitHub integration links Cumulus tasks to commits, branches, and pull requests.

## Installation

A workspace admin installs the Cumulus GitHub App from the GitHub Marketplace. Choose **All repositories** or pick specific repos. After install, go to **Settings → Integrations → GitHub** in Cumulus and map each Cumulus project to one or more GitHub repos.

## Linking commits and PRs

Mention a task ID in a commit message or PR title — `CUM-1234 fix login redirect` — and Cumulus auto-attaches the commit/PR to the task. The task's right-hand panel shows the linked commits and PR status (open, merged, closed).

## Automatic status transitions

If you turn on **Auto-transition** in the GitHub integration settings:

- Opening a PR moves the linked task to **In Review**.
- Merging the PR moves it to **Done**.
- Closing without merging moves it back to **In Progress**.

You can override per-project workflow mappings under **Project Settings → Workflow → Integrations**.

## Branch naming

If you want Cumulus to auto-link a branch, name it `<task-id>/short-description` — e.g. `CUM-1234/fix-login-redirect`. The integration scans new branches every 30 seconds.

## Permissions

The GitHub App requests **read** access to code and metadata, and **write** access to PRs (for posting status comments only). It does not request write access to your repo contents.
