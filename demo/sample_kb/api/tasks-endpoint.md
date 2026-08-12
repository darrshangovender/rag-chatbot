# Tasks API

All task endpoints are rooted at `https://api.cumulus.example/v1/tasks`.

## List tasks

`GET /v1/tasks?project_id=<id>&status=<status>&cursor=<cursor>`

Returns up to 100 tasks per page. Pagination is cursor-based — the response includes `next_cursor` if there are more results. Pass it back as the `cursor` query parameter.

Filters supported: `project_id`, `status`, `assignee_id`, `label`, `updated_after`, `created_after`.

## Get a task

`GET /v1/tasks/{task_id}`

Returns the task with all custom fields, current assignee, watchers, and the latest 20 comments.

## Create a task

`POST /v1/tasks` with body:

```json
{
  "project_id": "proj_abc",
  "title": "Fix login redirect on Safari",
  "assignee_id": "usr_xyz",
  "status": "Backlog",
  "due_date": "2026-07-01",
  "labels": ["bug", "ios"]
}
```

Required: `project_id`, `title`. Returns `201 Created` with the new task object including its generated `id`.

## Update a task

`PATCH /v1/tasks/{task_id}` — partial update, only include fields you want to change. Status transitions are validated against the project's workflow; an invalid transition returns `422`.

## Delete a task

`DELETE /v1/tasks/{task_id}` — soft-deletes. The task moves to the trash for 30 days, then is permanently removed. Restore from the trash via the UI or `POST /v1/tasks/{task_id}/restore`.
