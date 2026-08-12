# Automations

Automations are if-this-then-that rules that fire on task events. Set them up under **Project Settings → Automations**.

## Triggers

- Task created
- Status changed (with optional from/to filter)
- Assignee changed
- Due date passed
- Label added or removed
- Comment posted (with optional keyword filter)

## Actions

- Change status
- Change assignee (specific user, or "round-robin" within a group)
- Add or remove label
- Post a comment
- Send a Slack message to a channel
- Send a webhook to an external URL (Business and above)
- Create a follow-up task

## Quotas

Each automation rule can fire up to 1,000 times per workspace per day on Starter, 10,000 on Business, and unlimited on Enterprise. If you exceed the quota, further executions are queued until the next reset at 00:00 UTC.

## Debugging automations

Open the automation and click **Run history**. You'll see the last 200 executions with their trigger context, the actions that ran, and any errors. Failed actions are retried up to 3 times with exponential backoff (1s, 5s, 25s).

## Common recipes

- **Auto-assign by component**: when a task is labelled `frontend`, set assignee to the frontend on-call rotation.
- **Stale-task nag**: when a task has been In Review for more than 3 days, post a Slack reminder to the reviewer.
- **Release notes**: when a task moves to Done with the `customer-facing` label, append it to the current release notes doc.
