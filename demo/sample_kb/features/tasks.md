# Tasks

Tasks are the atomic unit of work in Cumulus. Every task belongs to exactly one project, has a status, an optional assignee, and an optional due date.

## Task statuses

The default workflow has four statuses: **Backlog**, **In Progress**, **In Review**, **Done**. You can customise the workflow per project from **Project Settings → Workflow**. Custom statuses are available on Business and Enterprise plans.

## Subtasks

A task can have up to 50 subtasks. Subtasks are themselves tasks — they can have assignees, due dates, and their own subtasks (up to three levels of nesting). When you mark a parent task as Done, you'll be prompted to close any open subtasks, but it's not mandatory.

## Dependencies

Mark task B as **blocked by** task A and Cumulus will surface the dependency in the sprint view. Dependencies do not auto-shift due dates — if A slips, B stays where it is and you'll see a "blocked" warning. Auto-shifting is on the roadmap for 2026.

## Bulk edit

Select multiple tasks with shift-click and press `e` to bulk-edit. You can change status, assignee, due date, project, or labels in one action. The undo button at the bottom of the screen is available for 30 seconds after a bulk edit.

## Task limits

A single project can hold up to 50,000 tasks. Above that, performance degrades on the list view; we recommend archiving completed sprints quarterly.
