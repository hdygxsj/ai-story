import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { WorkspaceTree, calculateTreeRelativeDropPosition, calculateWorkspaceDrop } from "../features/workspace/WorkspaceTree";
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
  it("converts Ant Design absolute drop positions to relative positions", () => {
    expect(calculateTreeRelativeDropPosition(-1, "0-0")).toBe(-1);
    expect(calculateTreeRelativeDropPosition(1, "0-0")).toBe(1);
    expect(calculateTreeRelativeDropPosition(1, "0-1")).toBe(0);
    expect(calculateTreeRelativeDropPosition(0, "0-1")).toBe(-1);
  });

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

  it("shows folder-specific copy when renaming a folder", async () => {
    const user = userEvent.setup();
    render(<WorkspaceTree nodes={nodes} />);

    await user.click(screen.getByRole("button", { name: "重命名 资料" }));

    expect(screen.getByText("重命名文件夹")).toBeInTheDocument();
    expect(screen.getByLabelText("文件夹名称")).toHaveValue("资料");
    expect(screen.queryByText("重命名章节")).not.toBeInTheDocument();
  });

  it("creates nodes from a folder context menu", async () => {
    const user = userEvent.setup();
    const onCreateChapter = vi.fn();
    const onCreateFolder = vi.fn();
    render(<WorkspaceTree nodes={nodes} onCreateChapter={onCreateChapter} onCreateFolder={onCreateFolder} />);

    await user.pointer({ keys: "[MouseRight]", target: screen.getByText("资料") });
    await user.click(await screen.findByRole("menuitem", { name: "新建章节" }));

    expect(onCreateChapter).toHaveBeenCalledWith("folder-1");

    await user.pointer({ keys: "[MouseRight]", target: screen.getByText("资料") });
    await user.click(await screen.findByRole("menuitem", { name: "新建文件夹" }));

    expect(onCreateFolder).toHaveBeenCalledWith("folder-1");
  });

  it("truncates long node titles instead of wrapping the tree row", () => {
    const longTitle = "这是一个非常非常非常长的章节标题应该只显示一行不能把章节树撑高";
    render(
      <WorkspaceTree
        nodes={[
          {
            id: "long-title",
            novel_id: "novel-1",
            parent_id: null,
            document_id: "doc-long",
            title: longTitle,
            node_type: "chapter",
            status: "draft",
            position: 0,
          },
        ]}
      />,
    );

    expect(screen.getByTestId("workspace-node-title-long-title")).toHaveStyle({
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap",
    });
    expect(screen.getByTestId("workspace-node-title-long-title")).toHaveAttribute("title", longTitle);
  });

  it("renders the node icon inline with the title in a single row", () => {
    render(<WorkspaceTree nodes={nodes} />);

    const folderTitle = screen.getByTestId("workspace-node-title-folder-1");
    const folderRow = folderTitle.parentElement as HTMLElement;
    expect(folderRow).toHaveStyle({ alignItems: "center", display: "inline-flex" });
    expect(folderRow.querySelector(".anticon-folder")).toBeTruthy();

    const chapterTitle = screen.getByTestId("workspace-node-title-chapter-1");
    const chapterRow = chapterTitle.parentElement as HTMLElement;
    expect(chapterRow.querySelector(".anticon-file-text")).toBeTruthy();
  });

  it("keeps tree nodes draggable without showing a drag-handle icon", () => {
    const { container } = render(<WorkspaceTree nodes={nodes} />);

    expect(container.querySelector(".ant-tree-treenode-draggable")).toBeTruthy();
    expect(container.querySelector(".ant-tree-draggable-icon")).not.toBeInTheDocument();
  });
});
