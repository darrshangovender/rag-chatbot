# Google Drive Integration

Attach Google Docs, Sheets, and Slides to Cumulus tasks with previews and permission sync.

## Installation

A workspace admin connects the integration at **Settings → Integrations → Google Drive**. Authorise with a Google account that has access to the relevant Drive content. The integration uses OAuth 2.0 with the `drive.readonly` scope.

## Attaching files

In any task or comment, click the **Attach** button and select **Google Drive**. A file picker shows files you can access. Selected files appear in the task's Attachments panel with the document title, last-modified date, and a thumbnail.

## Permission propagation

If a teammate doesn't have view access to an attached Google file, they see the file name and a **Request access** button that triggers the standard Google Drive access-request flow. Cumulus never copies file content into our database — only metadata and a thumbnail.

## Live preview

Click any attached Google file to open an in-line preview within Cumulus. Edits made in Google Drive appear in the preview after a refresh (preview cache is 60 seconds).

## Removing the integration

Disconnect at **Settings → Integrations → Google Drive → Disconnect**. Existing attachments remain on tasks as plain links — they just lose their thumbnail and live preview.
