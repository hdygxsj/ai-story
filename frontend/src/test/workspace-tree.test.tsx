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

  it("moves multiple selected chapters together above the first root item", () => {
    const changes = calculateWorkspaceDrop(nodes, {
      draggedId: "chapter-1",
      draggedIds: ["chapter-1", "chapter-2"],
      dropId: "folder-1",
      dropPosition: -1,
      dropToGap: true,
    });

    expect(changes).toContainEqual({ id: "chapter-1", parent_id: null, position: 0 });
    expect(changes).toContainEqual({ id: "chapter-2", parent_id: null, position: 1 });
    expect(changes).toContainEqual({ id: "folder-1", parent_id: null, position: 2 });
  });

  it("moves multiple selected chapters into a folder together", () => {
    const changes = calculateWorkspaceDrop(nodes, {
      draggedId: "chapter-1",
      draggedIds: ["chapter-1", "chapter-2"],
      dropId: "folder-1",
      dropPosition: 0,
      dropToGap: false,
    });

    expect(changes).toContainEqual({ id: "chapter-1", parent_id: "folder-1", position: 0 });
    expect(changes).toContainEqual({ id: "chapter-2", parent_id: "folder-1", position: 1 });
  });

  it("shows folder-specific copy when renaming a folder", async () => {
    const user = userEvent.setup();
    render(<WorkspaceTree nodes={nodes} />);

    await user.pointer({ keys: "[MouseRight]", target: screen.getByText("资料") });
    await user.click(await screen.findByRole("menuitem", { name: "重命名" }));

    expect(screen.getByText("重命名文件夹")).toBeInTheDocument();
    expect(screen.getByLabelText("文件夹名称")).toHaveValue("资料");
    expect(screen.queryByText("重命名章节")).not.toBeInTheDocument();
  });

  it("moves rename and delete actions into the node context menu", async () => {
    const user = userEvent.setup();
    const onTrashNode = vi.fn();
    render(<WorkspaceTree nodes={nodes} onTrashNode={onTrashNode} />);

    expect(screen.queryByRole("button", { name: "重命名 第一章" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "删除 第一章" })).not.toBeInTheDocument();

    await user.pointer({ keys: "[MouseRight]", target: screen.getByText("第一章") });
    await user.click(await screen.findByRole("menuitem", { name: "删除" }));

    expect(onTrashNode).toHaveBeenCalledWith("chapter-1");
  });

  it("creates nodes from the toolbar button", async () => {
    const user = userEvent.setup();
    const onCreateChapter = vi.fn();
    const onCreateFolder = vi.fn();
    render(<WorkspaceTree nodes={nodes} onCreateChapter={onCreateChapter} onCreateFolder={onCreateFolder} />);

    await user.click(screen.getByRole("button", { name: /新建/ }));
    await user.click(await screen.findByRole("menuitem", { name: "新建章节" }));

    expect(onCreateChapter).toHaveBeenCalledWith(null);

    await user.click(screen.getByRole("button", { name: /新建/ }));
    await user.click(await screen.findByRole("menuitem", { name: "新建文件夹" }));

    expect(onCreateFolder).toHaveBeenCalledWith(null);
  });

  it("exports chapters and folders from the node context menu", async () => {
    const user = userEvent.setup();
    const onExportNode = vi.fn();
    render(<WorkspaceTree nodes={nodes} onExportNode={onExportNode} />);

    await user.pointer({ keys: "[MouseRight]", target: screen.getByText("资料") });
    await user.click(await screen.findByRole("menuitem", { name: "导出 TXT" }));
    expect(onExportNode).toHaveBeenCalledWith("folder-1", "资料");

    await user.pointer({ keys: "[MouseRight]", target: screen.getByText("第一章") });
    await user.click(await screen.findByRole("menuitem", { name: "导出 TXT" }));
    expect(onExportNode).toHaveBeenCalledWith("chapter-1", "第一章");
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

  it("supports ctrl-click multi-select before dragging", async () => {
    const user = userEvent.setup();
    const onReorderNodes = vi.fn();
    render(<WorkspaceTree nodes={nodes} onReorderNodes={onReorderNodes} selectedDocumentId="doc-1" />);

    await user.click(screen.getByText("第一章"));
    await user.keyboard("{Control>}");
    await user.click(screen.getByText("第二章"));
    await user.keyboard("{/Control}");

    expect(screen.getByText("第一章").closest(".ant-tree-treenode-selected")).toBeTruthy();
    expect(screen.getByText("第二章").closest(".ant-tree-treenode-selected")).toBeTruthy();
  });

  it("keeps tree nodes draggable without showing a drag-handle icon", () => {
    const { container } = render(<WorkspaceTree nodes={nodes} />);

    expect(container.querySelector(".ant-tree-treenode-draggable")).toBeTruthy();
    expect(container.querySelector(".ant-tree-draggable-icon")).not.toBeInTheDocument();
  });

  it("collapses and expands the recycle bin section", async () => {
    const user = userEvent.setup();
    render(
      <WorkspaceTree
        nodes={[
          ...nodes,
          {
            id: "trashed-1",
            novel_id: "novel-1",
            parent_id: null,
            document_id: null,
            title: "已删除文件夹",
            node_type: "folder",
            status: "trashed",
            position: 0,
          },
        ]}
      />,
    );

    expect(screen.queryByRole("button", { name: "恢复 已删除文件夹" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "展开回收站" }));
    expect(screen.getByRole("button", { name: "恢复 已删除文件夹" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "收起回收站" }));
    expect(screen.queryByRole("button", { name: "恢复 已删除文件夹" })).not.toBeInTheDocument();
  });

  it("keeps the recycle bin in a separate bottom section", () => {
    render(
      <WorkspaceTree
        nodes={[
          ...nodes,
          {
            id: "trashed-bottom",
            novel_id: "novel-1",
            parent_id: null,
            document_id: null,
            title: "底部回收项",
            node_type: "folder",
            status: "trashed",
            position: 0,
          },
        ]}
      />,
    );

    const recycleBin = screen.getByLabelText("回收站");
    expect(recycleBin).toHaveStyle({ flex: "0 1 auto", maxHeight: "40%", overflow: "auto" });
    expect(recycleBin.parentElement).toHaveStyle({ display: "flex", flexDirection: "column", overflow: "hidden" });
  });
});
