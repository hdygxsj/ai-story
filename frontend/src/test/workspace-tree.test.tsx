import { describe, expect, it } from "vitest";

import { calculateWorkspaceDrop } from "../features/workspace/WorkspaceTree";
import type { WorkspaceNode } from "../api/workspace";

const nodes: WorkspaceNode[] = [
  {
    id: "folder-1",
    novel_id: "novel-1",
    parent_id: null,
    document_id: null,
    title: "资料",
    node_type: "folder",
    status: "draft",
    position: 0,
  },
  {
    id: "chapter-1",
    novel_id: "novel-1",
    parent_id: null,
    document_id: "doc-1",
    title: "第一章",
    node_type: "chapter",
    status: "draft",
    position: 1,
  },
  {
    id: "chapter-2",
    novel_id: "novel-1",
    parent_id: null,
    document_id: "doc-2",
    title: "第二章",
    node_type: "chapter",
    status: "draft",
    position: 2,
  },
];

describe("calculateWorkspaceDrop", () => {
  it("moves a dragged node above the first root item", () => {
    const changes = calculateWorkspaceDrop(nodes, {
      draggedId: "chapter-2",
      dropId: "folder-1",
      dropPosition: -1,
      dropToGap: true,
    });

    expect(changes).toContainEqual({ id: "chapter-2", parent_id: null, position: 0 });
    expect(changes).toContainEqual({ id: "folder-1", parent_id: null, position: 1 });
    expect(changes).toContainEqual({ id: "chapter-1", parent_id: null, position: 2 });
  });

  it("moves a chapter into a folder when dropped on the folder body", () => {
    const changes = calculateWorkspaceDrop(nodes, {
      draggedId: "chapter-1",
      dropId: "folder-1",
      dropPosition: 0,
      dropToGap: false,
    });

    expect(changes).toContainEqual({ id: "chapter-1", parent_id: "folder-1", position: 0 });
  });
});
