import { CaretRightOutlined, FileTextOutlined, FolderOutlined, LeftOutlined, PlusOutlined, UndoOutlined } from "@ant-design/icons";
import { Button, Dropdown, Input, Modal, Space, Tree, Typography } from "antd";
import type { MenuProps } from "antd";
import { useMemo, useState } from "react";
import type { WorkspaceNode } from "../../api/workspace";

type WorkspaceTreeProps = {
  nodes?: WorkspaceNode[];
  onCreateChapter?: (parentId?: string | null) => void;
  onCreateFolder?: (parentId?: string | null) => void;
  onCollapse?: () => void;
  onMoveNode?: (nodeId: string, parentId: string | null, position: number) => void;
  onReorderNodes?: (changes: WorkspaceNodePositionChange[]) => void;
  onRenameNode?: (nodeId: string, title: string) => void;
  onExportNode?: (nodeId: string, title: string) => void;
  onRestoreNode?: (nodeId: string) => void;
  onSelectDocument?: (documentId: string) => void;
  onTrashNode?: (nodeId: string) => void;
};

export type WorkspaceNodePositionChange = {
  id: string;
  parent_id: string | null;
  position: number;
};

type WorkspaceDropInput = {
  draggedId: string;
  dropId: string;
  dropPosition: number;
  dropToGap: boolean;
};

const placeholderNodes: WorkspaceNode[] = [
  {
    id: "drafts",
    novel_id: "placeholder",
    parent_id: null,
    document_id: null,
    title: "草稿",
    node_type: "folder",
    status: "draft",
    position: 0,
  },
  {
    id: "chapter-1",
    novel_id: "placeholder",
    parent_id: null,
    document_id: "chapter-1-doc",
    title: "第一章",
    node_type: "chapter",
    status: "draft",
    position: 1,
  },
];

function sortedSiblings(nodes: WorkspaceNode[], parentId: string | null) {
  return nodes
    .filter((node) => node.parent_id === parentId)
    .sort((left, right) => left.position - right.position || left.title.localeCompare(right.title));
}

function isDescendant(nodes: WorkspaceNode[], nodeId: string, possibleAncestorId: string): boolean {
  const nodesById = new Map(nodes.map((node) => [node.id, node]));
  let current = nodesById.get(nodeId);
  while (current?.parent_id) {
    if (current.parent_id === possibleAncestorId) {
      return true;
    }
    current = nodesById.get(current.parent_id);
  }
  return false;
}

export function calculateWorkspaceDrop(nodes: WorkspaceNode[], input: WorkspaceDropInput): WorkspaceNodePositionChange[] | null {
  const draggedNode = nodes.find((node) => node.id === input.draggedId);
  const dropNode = nodes.find((node) => node.id === input.dropId);
  if (!draggedNode || !dropNode || input.draggedId === input.dropId) {
    return null;
  }

  const nextParentId =
    !input.dropToGap && dropNode.node_type === "folder"
      ? dropNode.id
      : dropNode.parent_id;
  if (nextParentId === draggedNode.id || (nextParentId && isDescendant(nodes, nextParentId, draggedNode.id))) {
    return null;
  }

  const oldParentId = draggedNode.parent_id;
  const changes = new Map<string, WorkspaceNodePositionChange>();
  const targetSiblings = sortedSiblings(nodes, nextParentId).filter((node) => node.id !== draggedNode.id);
  const dropIndex = targetSiblings.findIndex((node) => node.id === input.dropId);
  const targetIndex =
    !input.dropToGap && dropNode.node_type === "folder"
      ? targetSiblings.length
      : input.dropPosition < 0
        ? Math.max(dropIndex, 0)
        : Math.max(dropIndex + 1, 0);
  const nextSiblings = [...targetSiblings];
  nextSiblings.splice(Math.min(targetIndex, nextSiblings.length), 0, draggedNode);

  nextSiblings.forEach((node, position) => {
    if (node.parent_id !== nextParentId || node.position !== position) {
      changes.set(node.id, { id: node.id, parent_id: nextParentId, position });
    }
  });

  if (oldParentId !== nextParentId) {
    sortedSiblings(nodes, oldParentId)
      .filter((node) => node.id !== draggedNode.id)
      .forEach((node, position) => {
        if (node.position !== position) {
          changes.set(node.id, { id: node.id, parent_id: oldParentId, position });
        }
      });
  }

  return [...changes.values()];
}

export function calculateTreeRelativeDropPosition(dropPosition: number, nodePosition?: string) {
  const treeIndex = Number(nodePosition?.split("-").at(-1));
  return Number.isFinite(treeIndex) ? dropPosition - treeIndex : dropPosition;
}

export function WorkspaceTree({
  nodes = placeholderNodes,
  onCreateChapter,
  onCreateFolder,
  onCollapse,
  onMoveNode,
  onReorderNodes,
  onExportNode,
  onRenameNode,
  onRestoreNode,
  onSelectDocument,
  onTrashNode,
}: WorkspaceTreeProps) {
  const [renamingNode, setRenamingNode] = useState<WorkspaceNode | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [recycleBinExpanded, setRecycleBinExpanded] = useState(true);
  const renamingNodeLabel = renamingNode?.node_type === "folder" ? "文件夹" : "章节";
  const activeNodes = useMemo(() => nodes.filter((node) => node.status !== "trashed"), [nodes]);
  const trashedNodes = useMemo(() => nodes.filter((node) => node.status === "trashed"), [nodes]);
  const childrenByParent = useMemo(() => {
    const map = new Map<string | null, WorkspaceNode[]>();
    for (const node of activeNodes) {
      const siblings = map.get(node.parent_id) ?? [];
      siblings.push(node);
      map.set(node.parent_id, siblings);
    }
    for (const siblings of map.values()) {
      siblings.sort((left, right) => left.position - right.position || left.title.localeCompare(right.title));
    }
    return map;
  }, [activeNodes]);

  function createContextMenu(parentId: string | null): MenuProps {
    return {
      items: [
        { key: "chapter", label: "新建章节" },
        { key: "folder", label: "新建文件夹" },
      ],
      onClick: ({ domEvent, key }) => {
        domEvent.stopPropagation();
        if (key === "chapter") {
          onCreateChapter?.(parentId);
        } else if (key === "folder") {
          onCreateFolder?.(parentId);
        }
      },
    };
  }

  function contextParentId(node: WorkspaceNode) {
    return node.node_type === "folder" ? node.id : node.parent_id;
  }

  function createNodeContextMenu(node: WorkspaceNode): MenuProps {
    const parentId = contextParentId(node);
    return {
      items: [
        { key: "chapter", label: "新建章节" },
        { key: "folder", label: "新建文件夹" },
        { type: "divider" },
        { key: "export", label: "导出 TXT" },
        { key: "rename", label: "重命名" },
        { danger: true, key: "trash", label: "删除" },
      ],
      onClick: ({ domEvent, key }) => {
        domEvent.stopPropagation();
        if (key === "chapter") {
          onCreateChapter?.(parentId);
        } else if (key === "folder") {
          onCreateFolder?.(parentId);
        } else if (key === "export") {
          onExportNode?.(node.id, node.title);
        } else if (key === "rename") {
          setRenamingNode(node);
          setRenameTitle(node.title);
        } else if (key === "trash") {
          onTrashNode?.(node.id);
        }
      },
    };
  }

  function buildTree(parentId: string | null): Array<Record<string, unknown>> {
    return (childrenByParent.get(parentId) ?? []).map((node) => ({
      key: node.id,
      title: (
        <Dropdown menu={createNodeContextMenu(node)} trigger={["contextMenu"]}>
          <span
            onContextMenu={(event) => event.stopPropagation()}
            style={{ alignItems: "center", display: "inline-flex", gap: 6, maxWidth: "100%", minWidth: 0, width: "100%" }}
          >
            <span aria-hidden style={{ alignItems: "center", color: "#94a3b8", display: "inline-flex", flexShrink: 0 }}>
              {node.node_type === "folder" ? <FolderOutlined /> : <FileTextOutlined />}
            </span>
            <span
              data-testid={`workspace-node-title-${node.id}`}
              title={node.title}
              style={{
                display: "inline-block",
                minWidth: 0,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {node.title}
            </span>
          </span>
        </Dropdown>
      ),
      children: buildTree(node.id),
      documentId: node.document_id,
    }));
  }

  const treeData = buildTree(null);

  function submitRename() {
    const nextTitle = renameTitle.trim();
    if (!renamingNode || !nextTitle) {
      return;
    }
    onRenameNode?.(renamingNode.id, nextTitle);
    setRenamingNode(null);
  }

  return (
    <>
      <Dropdown menu={createContextMenu(null)} trigger={["contextMenu"]}>
        <section
        aria-label="章节树"
        style={{
          background: "rgba(255,255,255,0.78)",
          border: "1px solid rgba(15,23,42,0.06)",
          borderRadius: 18,
          boxShadow: "0 18px 50px rgba(15,23,42,0.06)",
          display: "flex",
          flexDirection: "column",
          height: "100%",
          minWidth: 0,
          overflow: "hidden",
          padding: 14,
        }}
      >
        <div style={{ flex: "1 1 auto", minHeight: 0, overflow: "auto" }}>
          <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
          <div style={{ alignItems: "flex-start", display: "flex", justifyContent: "space-between", gap: 8 }}>
            <div>
              <Typography.Title level={2} style={{ marginBottom: 0 }}>
                章节
              </Typography.Title>
              <Typography.Text type="secondary">章节、草稿和笔记</Typography.Text>
            </div>
            {onCollapse ? (
              <Button aria-label="收起章节" icon={<LeftOutlined />} onClick={onCollapse} size="small" type="text" />
            ) : null}
          </div>
          <Dropdown menu={createContextMenu(null)} trigger={["click"]}>
            <Button icon={<PlusOutlined />} size="small" type="primary">
              新建
            </Button>
          </Dropdown>
          <Tree
            blockNode
            defaultExpandAll
            draggable={{ icon: false }}
            treeData={treeData}
            onDrop={(info) => {
              const draggedId = String(info.dragNode.key);
              const dropId = String(info.node.key);
              const changes = calculateWorkspaceDrop(activeNodes, {
                draggedId,
                dropId,
                dropPosition: calculateTreeRelativeDropPosition(
                  info.dropPosition,
                  (info.node as { pos?: string }).pos,
                ),
                dropToGap: info.dropToGap,
              });
              if (!changes?.length) {
                return;
              }
              onReorderNodes?.(changes);
              const draggedChange = changes.find((change) => change.id === draggedId);
              if (draggedChange && !onReorderNodes) {
                onMoveNode?.(draggedId, draggedChange.parent_id, draggedChange.position);
              }
            }}
            onSelect={(selectedKeys) => {
              const selectedKey = String(selectedKeys[0] ?? "");
              const documentId = nodes.find((node) => node.id === selectedKey)?.document_id;
              if (documentId) {
                onSelectDocument?.(documentId);
              }
            }}
          />
          </Space>
        </div>
          {trashedNodes.length > 0 ? (
            <div
              aria-label="回收站"
              style={{
                borderTop: "1px solid rgba(15,23,42,0.08)",
                flex: "0 1 auto",
                marginTop: 8,
                maxHeight: "40%",
                overflow: "auto",
                paddingTop: 10,
              }}
            >
              <button
                aria-expanded={recycleBinExpanded}
                aria-label={recycleBinExpanded ? "收起回收站" : "展开回收站"}
                onClick={() => setRecycleBinExpanded((current) => !current)}
                style={{
                  alignItems: "center",
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  display: "flex",
                  gap: 6,
                  padding: 0,
                  width: "100%",
                }}
                type="button"
              >
                <CaretRightOutlined
                  style={{
                    color: "#64748b",
                    fontSize: 12,
                    transform: recycleBinExpanded ? "rotate(90deg)" : "rotate(0deg)",
                    transition: "transform 0.2s ease",
                  }}
                />
                <Typography.Text strong>回收站</Typography.Text>
                <Typography.Text type="secondary">({trashedNodes.length})</Typography.Text>
              </button>
              {recycleBinExpanded ? (
                <Space direction="vertical" size={4} style={{ marginTop: 8, width: "100%" }}>
                  {trashedNodes.map((node) => (
                    <Button
                      aria-label={`恢复 ${node.title}`}
                      icon={<UndoOutlined />}
                      key={node.id}
                      onClick={() => onRestoreNode?.(node.id)}
                      size="small"
                      type="text"
                    >
                      {node.title}
                    </Button>
                  ))}
                </Space>
              ) : null}
            </div>
          ) : null}
      </section>
      </Dropdown>
      <Modal
        okText="确定"
        onCancel={() => setRenamingNode(null)}
        onOk={submitRename}
        open={Boolean(renamingNode)}
        title={`重命名${renamingNodeLabel}`}
      >
        <Input
          aria-label={`${renamingNodeLabel}名称`}
          autoFocus
          onChange={(event) => setRenameTitle(event.target.value)}
          onPressEnter={submitRename}
          value={renameTitle}
        />
      </Modal>
    </>
  );
}
