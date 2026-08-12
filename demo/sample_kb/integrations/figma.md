# Figma Integration

Embed Figma frames in Cumulus tasks and get auto-updating previews.

## Installation

A workspace admin enables the integration at **Settings → Integrations → Figma → Connect**. Authorise with your Figma account; the integration requests read access to file metadata only — it does not request access to file content.

## Embedding a frame

Paste any Figma URL into a task description or comment. Cumulus replaces the URL with a live preview that updates within ~30 seconds of the frame changing in Figma. Click the preview to open the original file in Figma.

## Permissions and visibility

Cumulus uses your personal Figma OAuth token to fetch previews. If a teammate views a task with a Figma embed they don't have access to in Figma, they'll see a placeholder ("You don't have permission to view this Figma frame") instead of the image.

## Branch-specific previews

For Figma files using branches, the embed always shows the main branch by default. To preview a specific branch, include the branch name in the URL fragment: `...?node-id=1:2&branch=feature-x`.

## Limits

There's a 25 MB cache per workspace for Figma preview images, refreshed daily. Workspaces with very large numbers of embeds may see slightly older previews on busy days.
