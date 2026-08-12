# Sprints

A sprint is a time-boxed batch of tasks. Cumulus supports sprints of any length from 3 to 28 days; the default is 14.

## Starting a sprint

From a project, click **Start sprint**. Pick a start date, an end date, and a name (e.g. "Sprint 42"). Drag tasks from the backlog into the sprint, or use the **Smart fill** button which suggests tasks based on priority, blockers cleared, and the team's historical velocity.

## During the sprint

The Active Sprint view shows a burndown chart, a kanban board, and an at-risk panel. A task is flagged "at risk" if its due date is in the past, it has zero activity in the last 3 days, or it has unresolved blocker dependencies.

## Ending a sprint

When the end date arrives, you'll be prompted to close the sprint. Closing moves incomplete tasks to one of three destinations of your choice:

1. Back to the backlog (default).
2. Into the next sprint, if one exists.
3. Into a new follow-up sprint that Cumulus creates for you.

Closed sprints are read-only and contribute to your team's velocity calculation.

## Velocity

Velocity is the rolling average story points completed across the last 6 closed sprints. It appears on the project dashboard. If a project has fewer than 3 closed sprints, velocity is shown as "not enough data."

## Multiple active sprints

Business plans and above allow up to 3 concurrent sprints per project (e.g. for parallel feature streams). Free and Starter are limited to one active sprint at a time.
