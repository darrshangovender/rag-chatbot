# Custom Fields

Custom fields let you attach structured metadata to tasks beyond the built-in attributes. Available on Business and Enterprise plans.

## Field types

- **Text** (up to 500 characters)
- **Number** (integer or decimal, with optional unit suffix)
- **Date**
- **Dropdown** (single-select)
- **Multi-select**
- **Person** (links to a workspace member)
- **URL**
- **Checkbox**

## Scope

Custom fields are defined at the project level. A workspace can have up to 30 custom fields per project, and 150 distinct field definitions across all projects. To re-use a definition across projects, mark it as **Workspace-level** when creating it — only workspace admins can do this.

## Filtering and reporting

Custom fields are first-class in CQL. For example:
`status = "In Progress" AND customer_tier = "Enterprise"`

They also appear as filter chips on the project list view and as group-by options on dashboards.

## Migration from labels

If you've been using labels as ad-hoc fields (e.g. labels like `tier:gold`, `tier:silver`), there's a migration tool at **Project Settings → Labels → Convert to custom field**. Pick the label prefix and Cumulus will create a dropdown field with the suffix values as options.

## API access

Custom field values are exposed in the REST API under `task.custom_fields` as a dict keyed by field ID. Field metadata (type, options) is available at `GET /v1/projects/{id}/fields`.
