import { CaretRightOutlined, FileTextOutlined, FolderOutlined, LeftOutlined, PlusOutlined, ReloadOutlined, UndoOutlined } from "@ant-design/icons";
import { Button, Dropdown, Input, Modal, Space, Tag, Tree, Typography } from "antd";
import type { MenuProps } from "antd";
import type { Key } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
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
  pendingWriteCountsByDocumentId?: Record<string, number>;
  onLocatePendingWrites?: (documentId: string) => void;
  onRefresh?: () => void;
  refreshing?: boolean;
  selectedDocumentId?: string | null;
};

export type WorkspaceNodePositionChange = {
  id: string;
  parent_id: string | null;
  position: number;
};

type WorkspaceDropInput = {
  draggedId: string;
  draggedIds?: string[];
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

function rectsIntersect(
  left: { left: number; top: number; right: number; bottom: number },
  right: { left: number; top: number; right: number; bottom: number },
) {
  return left.left < right.right && left.right > right.left && left.top < right.bottom && left.bottom > right.top;
}

export function normalizeMarqueeRect(startX: number, startY: number, endX: number, endY: number) {
  return {
    left: Math.min(startX, endX),
    top: Math.min(startY, endY),
    right: Math.max(startX, endX),
    bottom: Math.max(startY, endY),
  };
}

export function collectMarqueeNodeIds(
  container: HTMLElement,
  selectionRect: { left: number; top: number; right: number; bottom: number },
): string[] {
  const ids: string[] = [];
  for (const element of container.querySelectorAll("[data-workspace-node-id]")) {
    const nodeId = element.getAttribute("data-workspace-node-id");
    if (!nodeId) {
      continue;
    }
    const row = element.closest(".ant-tree-treenode");
    const target = row ?? element;
    const rect = target.getBoundingClientRect();
    if (rectsIntersect(selectionRect, rect)) {
      ids.push(nodeId);
    }
  }
  return ids;
}

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

function siblingRangeKeys(nodes: WorkspaceNode[], anchorKey: string, targetKey: string): string[] {
  const anchor = nodes.find((node) => node.id === anchorKey);
  const target = nodes.find((node) => node.id === targetKey);
  if (!anchor || !target || anchor.parent_id !== target.parent_id) {
    return [targetKey];
  }
  const siblings = sortedSiblings(nodes, anchor.parent_id);
  const anchorIndex = siblings.findIndex((node) => node.id === anchorKey);
  const targetIndex = siblings.findIndex((node) => node.id === targetKey);
  const [start, end] = anchorIndex < targetIndex ? [anchorIndex, targetIndex] : [targetIndex, anchorIndex];
  return siblings.slice(start, end + 1).map((node) => node.id);
}

function resolveMovableIds(nodes: WorkspaceNode[], draggedId: string, draggedIds?: string[]): string[] {
  const draggedNode = nodes.find((node) => node.id === draggedId);
  if (!draggedNode) {
    return [];
  }
  const requestedIds = draggedIds?.length ? draggedIds : [draggedId];
  const movableIds = [...new Set(requestedIds)]
    .filter((id) => {
      if (id === draggedId) {
        return true;
      }
      const node = nodes.find((item) => item.id === id);
      return node?.parent_id === draggedNode.parent_id;
    })
    .sort((leftId, rightId) => {
      const left = nodes.find((node) => node.id === leftId)!;
      const right = nodes.find((node) => node.id === rightId)!;
      return left.position - right.position || left.title.localeCompare(right.title);
    });
  return movableIds.includes(draggedId) ? movableIds : [...movableIds, draggedId];
}

function resolveInsertIndex(
  nodes: WorkspaceNode[],
  movableSet: Set<string>,
  nextParentId: string | null,
  dropId: string,
  dropPosition: number,
  dropToGap: boolean,
  dropNode: WorkspaceNode,
): number | null {
  const targetSiblings = sortedSiblings(nodes, nextParentId).filter((node) => !movableSet.has(node.id));

  if (!dropToGap && dropNode.node_type === "folder" && !movableSet.has(dropNode.id)) {
    return targetSiblings.length;
  }

  if (movableSet.has(dropId)) {
    if (!dropToGap) {
      return null;
    }
    const siblings = sortedSiblings(nodes, dropNode.parent_id);
    const dropIndex = siblings.findIndex((node) => node.id === dropId);
    if (dropPosition < 0) {
      let index = dropIndex - 1;
      while (index >= 0 && movableSet.has(siblings[index].id)) {
        index -= 1;
      }
      if (index < 0) {
        return 0;
      }
      const referenceIndex = targetSiblings.findIndex((node) => node.id === siblings[index].id);
      return referenceIndex < 0 ? 0 : referenceIndex + 1;
    }
    let index = dropIndex + 1;
    while (index < siblings.length && movableSet.has(siblings[index].id)) {
      index += 1;
    }
    if (index >= siblings.length) {
      return targetSiblings.length;
    }
    const referenceIndex = targetSiblings.findIndex((node) => node.id === siblings[index].id);
    return referenceIndex < 0 ? targetSiblings.length : referenceIndex;
  }

  const dropIndex = targetSiblings.findIndex((node) => node.id === dropId);
  return dropPosition < 0 ? Math.max(dropIndex, 0) : Math.max(dropIndex + 1, 0);
}

export function calculateWorkspaceDrop(nodes: WorkspaceNode[], input: WorkspaceDropInput): WorkspaceNodePositionChange[] | null {
  const draggedNode = nodes.find((node) => node.id === input.draggedId);
  const dropNode = nodes.find((node) => node.id === input.dropId);
  if (!draggedNode || !dropNode || input.draggedId === input.dropId) {
    return null;
  }

  const movableIds = resolveMovableIds(nodes, input.draggedId, input.draggedIds);
  const movableSet = new Set(movableIds);

  const nextParentId =
    !input.dropToGap && dropNode.node_type === "folder"
      ? dropNode.id
      : dropNode.parent_id;
  if (nextParentId === draggedNode.id || (nextParentId && isDescendant(nodes, nextParentId, draggedNode.id))) {
    return null;
  }
  for (const movableId of movableIds) {
    if (nextParentId === movableId || (nextParentId && isDescendant(nodes, nextParentId, movableId))) {
      return null;
    }
  }

  const insertIndex = resolveInsertIndex(
    nodes,
    movableSet,
    nextParentId,
    input.dropId,
    input.dropPosition,
    input.dropToGap,
    dropNode,
  );
  if (insertIndex === null) {
    return null;
  }

  const oldParentId = draggedNode.parent_id;
  const changes = new Map<string, WorkspaceNodePositionChange>();
  const targetSiblings = sortedSiblings(nodes, nextParentId).filter((node) => !movableSet.has(node.id));
  const movableNodes = movableIds.map((id) => nodes.find((node) => node.id === id)!);
  const nextSiblings = [...targetSiblings];
  nextSiblings.splice(Math.min(insertIndex, nextSiblings.length), 0, ...movableNodes);

  nextSiblings.forEach((node, position) => {
    if (node.parent_id !== nextParentId || node.position !== position) {
      changes.set(node.id, { id: node.id, parent_id: nextParentId, position });
    }
  });

  if (oldParentId !== nextParentId) {
    sortedSiblings(nodes, oldParentId)
      .filter((node) => !movableSet.has(node.id))
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

type MarqueeDrag = {
  additive: boolean;
  endX: number;
  endY: number;
  shift: boolean;
  startX: number;
  startY: number;
  targetNodeId: string | null;
};

const MARQUEE_MOVE_THRESHOLD = 4;

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
  onLocatePendingWrites,
  onRefresh,
  pendingWriteCountsByDocumentId = {},
  refreshing = false,
  selectedDocumentId = null,
}: WorkspaceTreeProps) {
  const [renamingNode, setRenamingNode] = useState<WorkspaceNode | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [recycleBinExpanded, setRecycleBinExpanded] = useState(false);
  const [selectedNodeKeys, setSelectedNodeKeys] = useState<string[]>([]);
  const [lastClickedNodeKey, setLastClickedNodeKey] = useState<string | null>(null);
  const [marquee, setMarquee] = useState<MarqueeDrag | null>(null);
  const [marqueeSelecting, setMarqueeSelecting] = useState(false);
  const previousDocumentIdRef = useRef<string | null>(null);
  const treeAreaRef = useRef<HTMLDivElement | null>(null);
  const marqueeDragRef = useRef<MarqueeDrag | null>(null);
  const marqueeSuppressSelectRef = useRef(false);
  const lastClickedNodeKeyRef = useRef(lastClickedNodeKey);
  lastClickedNodeKeyRef.current = lastClickedNodeKey;
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
              data-workspace-node-id={node.id}
              title={node.title}
              style={{
                display: "inline-block",
                flex: 1,
                minWidth: 0,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {node.title}
            </span>
            {node.document_id && (pendingWriteCountsByDocumentId[node.document_id] ?? 0) > 0 ? (
              <Tag
                color="gold"
                data-testid={`workspace-node-pending-write-${node.id}`}
                onClick={(event) => {
                  event.stopPropagation();
                  if (node.document_id) {
                    onLocatePendingWrites?.(node.document_id);
                  }
                }}
                style={{
                  cursor: onLocatePendingWrites ? "pointer" : "default",
                  flexShrink: 0,
                  fontSize: 10,
                  lineHeight: "16px",
                  margin: 0,
                  paddingInline: 4,
                }}
              >
                {pendingWriteCountsByDocumentId[node.document_id]} 处待确认
              </Tag>
            ) : null}
          </span>
        </Dropdown>
      ),
      children: buildTree(node.id),
      documentId: node.document_id,
    }));
  }

  const treeData = buildTree(null);

  useEffect(() => {
    if (selectedDocumentId === previousDocumentIdRef.current) {
      return;
    }
    previousDocumentIdRef.current = selectedDocumentId;
    if (!selectedDocumentId) {
      return;
    }
    const selectedNode = activeNodes.find((node) => node.document_id === selectedDocumentId);
    if (!selectedNode) {
      return;
    }
    setSelectedNodeKeys([selectedNode.id]);
    setLastClickedNodeKey(selectedNode.id);
  }, [activeNodes, selectedDocumentId]);

  useEffect(() => {
    function handleMouseMove(event: MouseEvent) {
      const drag = marqueeDragRef.current;
      if (!drag) {
        return;
      }

      drag.endX = event.clientX;
      drag.endY = event.clientY;
      const movedEnough =
        Math.abs(drag.endX - drag.startX) > MARQUEE_MOVE_THRESHOLD ||
        Math.abs(drag.endY - drag.startY) > MARQUEE_MOVE_THRESHOLD;

      if (!movedEnough) {
        return;
      }

      if (!marqueeSelecting) {
        setMarqueeSelecting(true);
        marqueeSuppressSelectRef.current = true;
      }
      setMarquee({ ...drag });
    }

    function finishMarquee(event: MouseEvent) {
      const drag = marqueeDragRef.current;
      if (!drag) {
        return;
      }

      const container = treeAreaRef.current;
      const movedEnough =
        Math.abs(event.clientX - drag.startX) > MARQUEE_MOVE_THRESHOLD ||
        Math.abs(event.clientY - drag.startY) > MARQUEE_MOVE_THRESHOLD;

      if (container && movedEnough) {
        const selectionRect = normalizeMarqueeRect(drag.startX, drag.startY, event.clientX, event.clientY);
        const marqueeIds = collectMarqueeNodeIds(container, selectionRect);
        if (marqueeIds.length) {
          setSelectedNodeKeys((currentKeys) => {
            const nextKeys = drag.additive ? [...new Set([...currentKeys, ...marqueeIds])] : marqueeIds;
            return nextKeys;
          });
          setLastClickedNodeKey(marqueeIds[marqueeIds.length - 1] ?? null);
          const documentId = [...marqueeIds]
            .reverse()
            .map((id) => activeNodes.find((node) => node.id === id)?.document_id)
            .find(Boolean);
          if (documentId) {
            onSelectDocument?.(documentId);
          }
        }
      } else if (!movedEnough && drag.shift && drag.targetNodeId) {
        const rangeKeys =
          lastClickedNodeKeyRef.current
            ? siblingRangeKeys(activeNodes, lastClickedNodeKeyRef.current, drag.targetNodeId)
            : [drag.targetNodeId];
        setSelectedNodeKeys(rangeKeys);
        setLastClickedNodeKey(drag.targetNodeId);
        const documentId = activeNodes.find((node) => node.id === drag.targetNodeId)?.document_id;
        if (documentId) {
          onSelectDocument?.(documentId);
        }
      }

      marqueeDragRef.current = null;
      setMarquee(null);
      setMarqueeSelecting(false);
      window.setTimeout(() => {
        marqueeSuppressSelectRef.current = false;
      }, 0);
    }

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", finishMarquee);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", finishMarquee);
    };
  }, [activeNodes, marqueeSelecting, onSelectDocument]);

  function shouldStartMarquee(target: EventTarget | null) {
    if (!(target instanceof Element) || !treeAreaRef.current?.contains(target)) {
      return false;
    }
    if (target.closest("button") || target.closest(".ant-tree-switcher")) {
      return false;
    }
    return true;
  }

  function handleTreeAreaMouseDownCapture(event: React.MouseEvent<HTMLDivElement>) {
    if (event.button !== 0 || !shouldStartMarquee(event.target)) {
      return;
    }

    const target = event.target as Element;
    const additive = event.ctrlKey || event.metaKey;
    const shift = event.shiftKey;
    const onContent = target.closest(".ant-tree-node-content-wrapper");
    const canMarquee = !onContent || shift;

    if (!canMarquee) {
      return;
    }

    const drag: MarqueeDrag = {
      additive,
      endX: event.clientX,
      endY: event.clientY,
      shift,
      startX: event.clientX,
      startY: event.clientY,
      targetNodeId:
        target.closest(".ant-tree-treenode")?.querySelector("[data-workspace-node-id]")?.getAttribute("data-workspace-node-id") ??
        null,
    };
    marqueeDragRef.current = drag;
    event.preventDefault();
    event.stopPropagation();

    if (!onContent) {
      setMarqueeSelecting(true);
      marqueeSuppressSelectRef.current = true;
      setMarquee({ ...drag });
    }
  }

  function handleNodeSelect(_selectedKeys: Key[], info: { nativeEvent: MouseEvent; node: { key: Key } }) {
    if (marqueeSuppressSelectRef.current || marqueeSelecting || marqueeDragRef.current) {
      return;
    }
    const clickedKey = String(info.node.key);
    const clickedNode = activeNodes.find((node) => node.id === clickedKey);
    const nativeEvent = info.nativeEvent;

    if (nativeEvent.shiftKey && lastClickedNodeKey) {
      setSelectedNodeKeys(siblingRangeKeys(activeNodes, lastClickedNodeKey, clickedKey));
    } else if (nativeEvent.ctrlKey || nativeEvent.metaKey) {
      const nextKeys = selectedNodeKeys.includes(clickedKey)
        ? selectedNodeKeys.filter((key) => key !== clickedKey)
        : [...selectedNodeKeys, clickedKey];
      setSelectedNodeKeys(nextKeys.length ? nextKeys : [clickedKey]);
      setLastClickedNodeKey(clickedKey);
    } else {
      setSelectedNodeKeys([clickedKey]);
      setLastClickedNodeKey(clickedKey);
    }

    if (clickedNode?.document_id) {
      onSelectDocument?.(clickedNode.document_id);
    }
  }

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
        <div style={{ flex: "1 1 0", minHeight: 0, overflow: "auto" }}>
          <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
          <div style={{ alignItems: "flex-start", display: "flex", justifyContent: "space-between", gap: 8 }}>
            <div>
              <Typography.Title level={2} style={{ marginBottom: 0 }}>
                章节
              </Typography.Title>
              <Typography.Text type="secondary">章节、草稿和笔记</Typography.Text>
            </div>
            <Space size={4}>
              <Dropdown menu={createContextMenu(null)} trigger={["click"]}>
                <Button icon={<PlusOutlined />} size="small" type="primary">
                  新建
                </Button>
              </Dropdown>
              {onRefresh ? (
                <Button
                  aria-label="刷新章节"
                  data-testid="workspace-tree-refresh"
                  icon={<ReloadOutlined />}
                  loading={refreshing}
                  onClick={onRefresh}
                  size="small"
                />
              ) : null}
              {onCollapse ? (
                <Button aria-label="收起章节" icon={<LeftOutlined />} onClick={onCollapse} size="small" type="text" />
              ) : null}
            </Space>
          </div>
          <div
            data-tree-marquee-area
            onMouseDownCapture={handleTreeAreaMouseDownCapture}
            ref={treeAreaRef}
            style={{ minHeight: 160, position: "relative", userSelect: marquee ? "none" : undefined }}
          >
            {marquee ? (
              <div
                aria-hidden
                style={{
                  background: "rgba(59, 130, 246, 0.14)",
                  border: "1px solid rgba(59, 130, 246, 0.45)",
                  left: normalizeMarqueeRect(marquee.startX, marquee.startY, marquee.endX, marquee.endY).left,
                  pointerEvents: "none",
                  position: "fixed",
                  top: normalizeMarqueeRect(marquee.startX, marquee.startY, marquee.endX, marquee.endY).top,
                  width:
                    normalizeMarqueeRect(marquee.startX, marquee.startY, marquee.endX, marquee.endY).right -
                    normalizeMarqueeRect(marquee.startX, marquee.startY, marquee.endX, marquee.endY).left,
                  height:
                    normalizeMarqueeRect(marquee.startX, marquee.startY, marquee.endX, marquee.endY).bottom -
                    normalizeMarqueeRect(marquee.startX, marquee.startY, marquee.endX, marquee.endY).top,
                  zIndex: 20,
                }}
              />
            ) : null}
            <Tree
            blockNode
            defaultExpandAll
            draggable={marqueeSelecting ? false : { icon: false }}
            multiple
            selectedKeys={selectedNodeKeys}
            treeData={treeData}
            onDrop={(info) => {
              const draggedId = String(info.dragNode.key);
              const dropId = String(info.node.key);
              const draggedIds = selectedNodeKeys.includes(draggedId) ? selectedNodeKeys : [draggedId];
              const changes = calculateWorkspaceDrop(activeNodes, {
                draggedId,
                draggedIds,
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
            onSelect={handleNodeSelect}
          />
          </div>
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
                minHeight: 0,
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
