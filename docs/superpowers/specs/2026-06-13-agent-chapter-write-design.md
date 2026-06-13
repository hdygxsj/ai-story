# Agent Chapter Write Design

## Goal

When the user asks the Agent to write a chapter into the workspace, the Agent must create the chapter node and persist its non-empty document content before claiming success.

## Design

- Add one runtime tool, `create_chapter_with_content`, with novel ID, title, content, and optional parent folder ID.
- The service creates the document, chapter node, initial document version, and RAG index as one operation. It returns the created node plus the refreshed workspace tree.
- The Agent prompt explicitly distinguishes drafting in chat from writing into the workspace. It may say a chapter was saved only after the write tool succeeds.
- Existing `workspace_nodes` response data carries the created chapter to the frontend. The workspace selects the newly created document and loads its content.
- Empty chapter content is rejected, preventing a successful response that leaves an empty file.

## Verification

- A runtime-tool test proves the node and non-empty document are persisted.
- An Agent graph test proves the write tool result is surfaced as a workspace mutation.
- A frontend test proves a returned chapter is selected and displayed.
