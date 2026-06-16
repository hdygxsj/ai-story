import {
  CompressOutlined,
  ExpandOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
} from "@ant-design/icons";
import { Button, Modal, Space, Tooltip } from "antd";
import { useCallback, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import type { RelationshipEdge } from "../../api/materials";
import { buildRelationshipNetworkNodes, type GraphNode } from "./relationshipGraphLayout";
import {
  DEFAULT_GRAPH_VIEW_TRANSFORM,
  GRAPH_ZOOM_STEP,
  type GraphViewTransform,
  graphViewBox,
  panGraphView,
  zoomGraphAroundCenter,
  zoomGraphAtPoint,
} from "./relationshipGraphView";

type PositionedEdge = RelationshipEdge & {
  path: string;
  labelX: number;
  labelY: number;
  pairKey: string;
  pairIndex: number;
  pairTotal: number;
};

const NODE_RADIUS = 28;

type RelationshipColor = {
  stroke: string;
  strokeActive: string;
  label: string;
  labelActive: string;
};

const RELATIONSHIP_COLORS: RelationshipColor[] = [
  { stroke: "rgba(234, 88, 12, 0.5)", strokeActive: "rgba(234, 88, 12, 0.95)", label: "#c2410c", labelActive: "#9a3412" },
  { stroke: "rgba(37, 99, 235, 0.5)", strokeActive: "rgba(37, 99, 235, 0.95)", label: "#1d4ed8", labelActive: "#1e3a8a" },
  { stroke: "rgba(124, 58, 237, 0.5)", strokeActive: "rgba(124, 58, 237, 0.95)", label: "#6d28d9", labelActive: "#5b21b6" },
  { stroke: "rgba(5, 150, 105, 0.5)", strokeActive: "rgba(5, 150, 105, 0.95)", label: "#047857", labelActive: "#065f46" },
  { stroke: "rgba(225, 29, 72, 0.5)", strokeActive: "rgba(225, 29, 72, 0.95)", label: "#be123c", labelActive: "#9f1239" },
  { stroke: "rgba(13, 148, 136, 0.5)", strokeActive: "rgba(13, 148, 136, 0.95)", label: "#0f766e", labelActive: "#115e59" },
  { stroke: "rgba(217, 119, 6, 0.5)", strokeActive: "rgba(217, 119, 6, 0.95)", label: "#b45309", labelActive: "#92400e" },
  { stroke: "rgba(79, 70, 229, 0.5)", strokeActive: "rgba(79, 70, 229, 0.95)", label: "#4338ca", labelActive: "#3730a3" },
];

const DIMMED_STROKE = "rgba(148, 163, 184, 0.28)";
const DIMMED_LABEL = "rgba(100, 116, 139, 0.72)";

function relationshipEdgeKey(edge: RelationshipEdge) {
  return `${edge.source_character}\0${edge.target_character}\0${edge.relationship_type}`;
}

export function dedupeRelationshipEdges(edges: RelationshipEdge[]): {
  edges: RelationshipEdge[];
  hiddenCount: number;
} {
  const byKey = new Map<string, RelationshipEdge>();
  for (const edge of edges) {
    const key = relationshipEdgeKey(edge);
    const existing = byKey.get(key);
    if (!existing || (edge.description?.length ?? 0) >= (existing.description?.length ?? 0)) {
      byKey.set(key, edge);
    }
  }
  const uniqueEdges = Array.from(byKey.values());
  return {
    edges: uniqueEdges,
    hiddenCount: Math.max(0, edges.length - uniqueEdges.length),
  };
}

function buildRelationshipColorMap(edges: RelationshipEdge[]): Map<string, RelationshipColor> {
  const types = Array.from(new Set(edges.map((edge) => edge.relationship_type))).sort((left, right) =>
    left.localeCompare(right, "zh-CN"),
  );

  return new Map(
    types.map((type, index) => [type, RELATIONSHIP_COLORS[index % RELATIONSHIP_COLORS.length]!]),
  );
}

function edgePath(
  source: GraphNode,
  target: GraphNode,
  pairIndex: number,
  pairTotal: number,
): { path: string; labelX: number; labelY: number } {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const length = Math.hypot(dx, dy) || 1;
  const offset = (pairIndex - (pairTotal - 1) / 2) * 28;
  const controlX = (source.x + target.x) / 2 - (dy / length) * offset;
  const controlY = (source.y + target.y) / 2 + (dx / length) * offset;
  const labelX = 0.25 * source.x + 0.5 * controlX + 0.25 * target.x;
  const labelY = 0.25 * source.y + 0.5 * controlY + 0.25 * target.y;

  return {
    path: `M ${source.x} ${source.y} Q ${controlX} ${controlY} ${target.x} ${target.y}`,
    labelX,
    labelY,
  };
}

function buildPositionedEdges(edges: RelationshipEdge[], nodes: GraphNode[]): PositionedEdge[] {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const pairCounts = new Map<string, number>();
  const pairSeen = new Map<string, number>();

  for (const edge of edges) {
    const pairKey = `${edge.source_character}::${edge.target_character}`;
    pairCounts.set(pairKey, (pairCounts.get(pairKey) ?? 0) + 1);
  }

  return edges.map((edge) => {
    const source = nodeById.get(edge.source_character);
    const target = nodeById.get(edge.target_character);
    if (!source || !target) {
      return {
        ...edge,
        path: "",
        labelX: 0,
        labelY: 0,
        pairKey: "",
        pairIndex: 0,
        pairTotal: 1,
      };
    }

    const pairKey = `${edge.source_character}::${edge.target_character}`;
    const pairIndex = pairSeen.get(pairKey) ?? 0;
    pairSeen.set(pairKey, pairIndex + 1);
    const pairTotal = pairCounts.get(pairKey) ?? 1;
    const geometry = edgePath(source, target, pairIndex, pairTotal);

    return {
      ...edge,
      ...geometry,
      pairKey,
      pairIndex,
      pairTotal,
    };
  });
}

type RelationshipGraphCanvasProps = {
  activeEdgeId: string | null;
  graphInstanceId: string;
  highlightedEdgeIds: Set<string> | null;
  highlightedNodeIds: Set<string> | null;
  hoveredNodeId: string | null;
  onEdgeSelect: (edgeId: string) => void;
  onNodeHover: (nodeId: string | null) => void;
  positionedEdges: PositionedEdge[];
  relationshipColorIndex: Map<string, number>;
  relationshipColors: Map<string, RelationshipColor>;
  nodes: GraphNode[];
  viewTransform: GraphViewTransform;
};

function RelationshipGraphCanvas({
  activeEdgeId,
  graphInstanceId,
  highlightedEdgeIds,
  highlightedNodeIds,
  onEdgeSelect,
  onNodeHover,
  positionedEdges,
  relationshipColorIndex,
  relationshipColors,
  nodes,
  viewTransform,
}: RelationshipGraphCanvasProps) {
  return (
    <svg
      aria-label="人物关系图谱"
      className="relationship-graph-canvas"
      role="img"
      viewBox={graphViewBox(viewTransform)}
    >
      <defs>
        {Array.from(relationshipColors.entries()).map(([type, color], index) => (
          <marker
            id={`relationship-graph-arrow-${graphInstanceId}-${index}`}
            key={type}
            markerHeight="8"
            markerUnits="strokeWidth"
            markerWidth="8"
            orient="auto"
            refX="8"
            refY="4"
          >
            <path d="M 0 0 L 8 4 L 0 8 z" fill={color.strokeActive} />
          </marker>
        ))}
      </defs>

      {positionedEdges.map((edge) => {
        if (!edge.path) {
          return null;
        }

        const color = relationshipColors.get(edge.relationship_type);
        const colorIndex = relationshipColorIndex.get(edge.relationship_type) ?? -1;
        const isActive = activeEdgeId === edge.id;
        const isHighlighted = highlightedEdgeIds?.has(edge.id) ?? false;
        const isDimmed = highlightedEdgeIds !== null && !isHighlighted;
        const strokeColor = isDimmed ? DIMMED_STROKE : isActive ? color?.strokeActive : color?.stroke;
        const labelColor = isDimmed ? DIMMED_LABEL : isActive ? color?.labelActive : color?.label;

        return (
          <g key={edge.id}>
            <path
              className={[
                "relationship-graph-edge",
                isActive ? "relationship-graph-edge-active" : "",
                isDimmed ? "relationship-graph-edge-dimmed" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              d={edge.path}
              markerEnd={colorIndex >= 0 ? `url(#relationship-graph-arrow-${graphInstanceId}-${colorIndex})` : undefined}
              onClick={() => onEdgeSelect(edge.id)}
              style={{ stroke: strokeColor }}
            />
            <text
              className={[
                "relationship-graph-edge-label",
                isActive ? "relationship-graph-edge-label-active" : "",
                isDimmed ? "relationship-graph-edge-label-dimmed" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              dominantBaseline="middle"
              onClick={() => onEdgeSelect(edge.id)}
              style={{ fill: labelColor }}
              textAnchor="middle"
              x={edge.labelX}
              y={edge.labelY}
            >
              {edge.relationship_type}
            </text>
          </g>
        );
      })}

      {nodes.map((node) => {
        const isHighlighted = highlightedNodeIds?.has(node.id) ?? false;
        const isDimmed = highlightedNodeIds !== null && !isHighlighted;

        return (
          <g
            key={node.id}
            className={[
              "relationship-graph-node",
              isHighlighted ? "relationship-graph-node-active" : "",
              isDimmed ? "relationship-graph-node-dimmed" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            onMouseEnter={() => onNodeHover(node.id)}
            onMouseLeave={() => onNodeHover(null)}
          >
            <circle className="relationship-graph-node-circle" cx={node.x} cy={node.y} r={NODE_RADIUS} />
            <text
              className="relationship-graph-node-label"
              dominantBaseline="middle"
              textAnchor="middle"
              x={node.x}
              y={node.y}
            >
              {node.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

type RelationshipGraphViewportProps = {
  activeEdgeId: string | null;
  canvasClassName?: string;
  graphInstanceId: string;
  highlightedEdgeIds: Set<string> | null;
  highlightedNodeIds: Set<string> | null;
  hoveredNodeId: string | null;
  onEdgeSelect: (edgeId: string) => void;
  onNodeHover: (nodeId: string | null) => void;
  onTransformChange: (transform: GraphViewTransform) => void;
  onZoomReset: () => void;
  positionedEdges: PositionedEdge[];
  relationshipColorIndex: Map<string, number>;
  relationshipColors: Map<string, RelationshipColor>;
  nodes: GraphNode[];
  showFullscreen?: boolean;
  onOpenFullscreen?: () => void;
  viewTransform: GraphViewTransform;
};

function RelationshipGraphViewport({
  activeEdgeId,
  canvasClassName,
  graphInstanceId,
  highlightedEdgeIds,
  highlightedNodeIds,
  hoveredNodeId,
  onEdgeSelect,
  onNodeHover,
  onTransformChange,
  onZoomReset,
  onOpenFullscreen,
  positionedEdges,
  relationshipColorIndex,
  relationshipColors,
  nodes,
  showFullscreen = true,
  viewTransform,
}: RelationshipGraphViewportProps) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const panStateRef = useRef<{ clientX: number; clientY: number; transform: GraphViewTransform } | null>(null);
  const [isPanning, setIsPanning] = useState(false);

  const handleWheel = useCallback(
    (event: React.WheelEvent<HTMLDivElement>) => {
      event.preventDefault();
      const viewport = viewportRef.current;
      if (!viewport) {
        return;
      }
      const rect = viewport.getBoundingClientRect();
      const pointerRatioX = (event.clientX - rect.left) / rect.width;
      const pointerRatioY = (event.clientY - rect.top) / rect.height;
      const delta = event.deltaY < 0 ? 1.12 : 0.89;
      onTransformChange(zoomGraphAtPoint(viewTransform, viewTransform.zoom * delta, pointerRatioX, pointerRatioY));
    },
    [onTransformChange, viewTransform],
  );

  const handlePointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (event.button !== 0 || viewTransform.zoom <= 1) {
        return;
      }
      const target = event.target as HTMLElement;
      if (target.closest(".relationship-graph-edge, .relationship-graph-edge-label, .relationship-graph-node")) {
        return;
      }
      panStateRef.current = {
        clientX: event.clientX,
        clientY: event.clientY,
        transform: viewTransform,
      };
      setIsPanning(true);
      event.currentTarget.setPointerCapture(event.pointerId);
    },
    [viewTransform],
  );

  const handlePointerMove = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const panState = panStateRef.current;
      const viewport = viewportRef.current;
      if (!panState || !viewport) {
        return;
      }
      onTransformChange(
        panGraphView(
          panState.transform,
          event.clientX - panState.clientX,
          event.clientY - panState.clientY,
          viewport.clientWidth,
          viewport.clientHeight,
        ),
      );
    },
    [onTransformChange],
  );

  const handlePointerUp = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    panStateRef.current = null;
    setIsPanning(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }, []);

  return (
    <div
      className={[
        "relationship-graph-viewport",
        canvasClassName,
        isPanning ? "relationship-graph-viewport-panning" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onWheel={handleWheel}
      ref={viewportRef}
    >
      <div className="relationship-graph-toolbar">
        <Space.Compact>
          <Tooltip title="放大">
            <Button
              aria-label="放大关系图"
              icon={<ZoomInOutlined />}
              onClick={() => onTransformChange(zoomGraphAroundCenter(viewTransform, viewTransform.zoom + GRAPH_ZOOM_STEP))}
              size="small"
              type="default"
            />
          </Tooltip>
          <Tooltip title="缩小">
            <Button
              aria-label="缩小关系图"
              icon={<ZoomOutOutlined />}
              onClick={() => onTransformChange(zoomGraphAroundCenter(viewTransform, viewTransform.zoom - GRAPH_ZOOM_STEP))}
              size="small"
              type="default"
            />
          </Tooltip>
          <Tooltip title="重置缩放">
            <Button
              aria-label="重置关系图缩放"
              icon={<CompressOutlined />}
              onClick={onZoomReset}
              size="small"
              type="default"
            />
          </Tooltip>
          {showFullscreen && onOpenFullscreen ? (
            <Tooltip title="全屏查看">
              <Button
                aria-label="全屏查看关系图"
                icon={<ExpandOutlined />}
                onClick={onOpenFullscreen}
                size="small"
                type="default"
              />
            </Tooltip>
          ) : null}
        </Space.Compact>
        <span className="relationship-graph-zoom-indicator">{Math.round(viewTransform.zoom * 100)}%</span>
      </div>

      <RelationshipGraphCanvas
        activeEdgeId={activeEdgeId}
        graphInstanceId={graphInstanceId}
        highlightedEdgeIds={highlightedEdgeIds}
        highlightedNodeIds={highlightedNodeIds}
        hoveredNodeId={hoveredNodeId}
        nodes={nodes}
        onEdgeSelect={onEdgeSelect}
        onNodeHover={onNodeHover}
        positionedEdges={positionedEdges}
        relationshipColorIndex={relationshipColorIndex}
        relationshipColors={relationshipColors}
        viewTransform={viewTransform}
      />
    </div>
  );
}

type RelationshipGraphBodyProps = {
  activeEdge: PositionedEdge | null;
  activeEdgeColor: RelationshipColor | null | undefined;
  activeEdgeId: string | null;
  canvasClassName?: string;
  graphInstanceId: string;
  hiddenCount: number;
  highlightedEdgeIds: Set<string> | null;
  highlightedNodeIds: Set<string> | null;
  hoveredNodeId: string | null;
  onEdgeSelect: (edgeId: string) => void;
  onNodeHover: (nodeId: string | null) => void;
  onTransformChange: (transform: GraphViewTransform) => void;
  onZoomReset: () => void;
  positionedEdges: PositionedEdge[];
  relationshipColorIndex: Map<string, number>;
  relationshipColors: Map<string, RelationshipColor>;
  nodes: GraphNode[];
  showFullscreen?: boolean;
  onOpenFullscreen?: () => void;
  viewTransform: GraphViewTransform;
  visibleEdgeCount: number;
};

function RelationshipGraphBody({
  activeEdge,
  activeEdgeColor,
  activeEdgeId,
  canvasClassName,
  graphInstanceId,
  hiddenCount,
  highlightedEdgeIds,
  highlightedNodeIds,
  hoveredNodeId,
  onEdgeSelect,
  onNodeHover,
  onTransformChange,
  onZoomReset,
  onOpenFullscreen,
  positionedEdges,
  relationshipColorIndex,
  relationshipColors,
  nodes,
  showFullscreen,
  viewTransform,
  visibleEdgeCount,
}: RelationshipGraphBodyProps) {
  return (
    <>
      {hiddenCount > 0 ? (
        <p className="relationship-graph-dedupe-hint">
          已合并显示 {visibleEdgeCount} 条关系，隐藏了 {hiddenCount} 条重复记录。可在 Agent 对话中清理重复数据。
        </p>
      ) : null}

      <RelationshipGraphViewport
        activeEdgeId={activeEdgeId}
        canvasClassName={canvasClassName}
        graphInstanceId={graphInstanceId}
        highlightedEdgeIds={highlightedEdgeIds}
        highlightedNodeIds={highlightedNodeIds}
        hoveredNodeId={hoveredNodeId}
        nodes={nodes}
        onEdgeSelect={onEdgeSelect}
        onNodeHover={onNodeHover}
        onOpenFullscreen={onOpenFullscreen}
        onTransformChange={onTransformChange}
        onZoomReset={onZoomReset}
        positionedEdges={positionedEdges}
        relationshipColorIndex={relationshipColorIndex}
        relationshipColors={relationshipColors}
        showFullscreen={showFullscreen}
        viewTransform={viewTransform}
      />

      {relationshipColors.size > 1 ? (
        <div aria-label="关系类型图例" className="relationship-graph-legend">
          {Array.from(relationshipColors.entries()).map(([type, color]) => (
            <span className="relationship-graph-legend-item" key={type}>
              <span className="relationship-graph-legend-dot" style={{ backgroundColor: color.strokeActive }} />
              {type}
            </span>
          ))}
        </div>
      ) : null}

      <div aria-live="polite" className="relationship-graph-detail">
        {activeEdge ? (
          <>
            <p className="relationship-graph-detail-title">
              {activeEdge.source_character}
              <span className="relationship-graph-detail-arrow" style={{ color: activeEdgeColor?.strokeActive }}>
                →
              </span>
              {activeEdge.target_character}
            </p>
            <p className="relationship-graph-detail-type" style={{ color: activeEdgeColor?.labelActive }}>
              {activeEdge.relationship_type}
            </p>
            {activeEdge.description ? (
              <p className="relationship-graph-detail-description">{activeEdge.description}</p>
            ) : (
              <p className="relationship-graph-detail-description relationship-graph-detail-empty">暂无关系说明</p>
            )}
          </>
        ) : (
          <p className="relationship-graph-detail-hint">
            点击关系连线或标签查看详情，悬停角色可高亮相关关系；滚轮或工具栏可缩放，放大后可拖拽平移
          </p>
        )}
      </div>
    </>
  );
}

type RelationshipGraphProps = {
  edges: RelationshipEdge[];
};

export function RelationshipGraph({ edges }: RelationshipGraphProps) {
  const [activeEdgeId, setActiveEdgeId] = useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [viewTransform, setViewTransform] = useState<GraphViewTransform>(DEFAULT_GRAPH_VIEW_TRANSFORM);
  const [fullscreenOpen, setFullscreenOpen] = useState(false);
  const [fullscreenTransform, setFullscreenTransform] = useState<GraphViewTransform>(DEFAULT_GRAPH_VIEW_TRANSFORM);

  const { edges: visibleEdges, hiddenCount } = useMemo(() => dedupeRelationshipEdges(edges), [edges]);
  const nodes = useMemo(() => buildRelationshipNetworkNodes(visibleEdges), [visibleEdges]);
  const positionedEdges = useMemo(() => buildPositionedEdges(visibleEdges, nodes), [visibleEdges, nodes]);
  const relationshipColors = useMemo(() => buildRelationshipColorMap(visibleEdges), [visibleEdges]);
  const relationshipColorIndex = useMemo(
    () => new Map(Array.from(relationshipColors.keys()).map((type, index) => [type, index])),
    [relationshipColors],
  );
  const activeEdge = positionedEdges.find((edge) => edge.id === activeEdgeId) ?? null;
  const activeEdgeColor = activeEdge ? relationshipColors.get(activeEdge.relationship_type) : null;

  const highlightedNodeIds = useMemo(() => {
    if (!activeEdge) {
      return hoveredNodeId ? new Set([hoveredNodeId]) : null;
    }
    return new Set([activeEdge.source_character, activeEdge.target_character]);
  }, [activeEdge, hoveredNodeId]);

  const highlightedEdgeIds = useMemo(() => {
    if (!hoveredNodeId) {
      return activeEdge ? new Set([activeEdge.id]) : null;
    }
    return new Set(
      positionedEdges
        .filter((edge) => edge.source_character === hoveredNodeId || edge.target_character === hoveredNodeId)
        .map((edge) => edge.id),
    );
  }, [activeEdge, hoveredNodeId, positionedEdges]);

  const sharedBodyProps = {
    activeEdge,
    activeEdgeColor,
    activeEdgeId,
    hiddenCount,
    highlightedEdgeIds,
    highlightedNodeIds,
    hoveredNodeId,
    onEdgeSelect: setActiveEdgeId,
    onNodeHover: setHoveredNodeId,
    positionedEdges,
    relationshipColorIndex,
    relationshipColors,
    nodes,
    visibleEdgeCount: visibleEdges.length,
  };

  return (
    <div className="relationship-graph">
      <RelationshipGraphBody
        {...sharedBodyProps}
        graphInstanceId="inline"
        onOpenFullscreen={() => {
          setFullscreenTransform(viewTransform);
          setFullscreenOpen(true);
        }}
        onTransformChange={setViewTransform}
        onZoomReset={() => setViewTransform(DEFAULT_GRAPH_VIEW_TRANSFORM)}
        showFullscreen
        viewTransform={viewTransform}
      />

      <Modal
        className="relationship-graph-fullscreen-modal"
        destroyOnHidden
        footer={null}
        onCancel={() => setFullscreenOpen(false)}
        open={fullscreenOpen}
        title="人物关系图"
        width="min(1200px, 92vw)"
      >
        <div className="relationship-graph relationship-graph-fullscreen">
          <RelationshipGraphBody
            {...sharedBodyProps}
            canvasClassName="relationship-graph-viewport-fullscreen"
            graphInstanceId="fullscreen"
            onTransformChange={setFullscreenTransform}
            onZoomReset={() => setFullscreenTransform(DEFAULT_GRAPH_VIEW_TRANSFORM)}
            showFullscreen={false}
            viewTransform={fullscreenTransform}
          />
        </div>
      </Modal>
    </div>
  );
}
