# Workspace Layout Controls Design

## Goal

Give the writing editor more usable space by making the chapter tree collapsible, compacting the Agent controls, reducing the overview footprint, and making the Agent column resizable.

## Layout

- Keep the workspace as a single-height grid below the page header.
- The chapter tree occupies its persisted width while expanded. When collapsed, its column and resize separator are removed completely.
- A collapse button lives in the chapter panel header. While collapsed, an expand button appears at the upper-left edge of the editor column.
- The editor remains the flexible middle column.
- Add a resize separator immediately before the Agent column. The Agent width is clamped between 320 and 640 pixels and persisted in local storage.
- Move the work overview into a compact strip above the editor only. It must not consume vertical space above the Agent panel.

## Agent Header

- Keep the Agent title in the card header.
- Render the active conversation selector, create-conversation button, conversation menu, and context-settings button in the same header area.
- Remove the separate toolbar row from the Agent card body.
- Preserve existing conversation create, select, rename, delete, and context-settings behavior.

## Persistence And Accessibility

- Persist the chapter tree expanded/collapsed state in local storage.
- Preserve the existing persisted chapter width.
- Persist the Agent width in local storage.
- Resize handles use separator roles and descriptive accessible labels.
- Collapse and expand controls expose explicit accessible names.

## Testing

- Extend workspace component tests to cover chapter collapse/restore and persisted state.
- Cover Agent width dragging, clamping, and persistence.
- Verify the workspace grid changes when either side panel changes.
- Verify conversation controls remain available in the Agent header and the overview is scoped to the editor column.
- Run the focused frontend tests, then the frontend build.
