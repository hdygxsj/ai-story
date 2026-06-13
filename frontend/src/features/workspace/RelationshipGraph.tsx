import { useMemo, useState } from "react";

import type { RelationshipEdge } from "../../api/materials";

type GraphNode = {
  id: string;
  label: string;
  x: number;
  y: number;
};

type PositionedEdge = RelationshipEdge & {
  path: string;
  labelX: number;
  labelY: number;
  pairKey: string;
  pairIndex: number;
  pairTotal: number;
};

const GRAPH_SIZE = 520;
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

function buildNodes(edges: RelationshipEdge[]): GraphNode[] {
  const names = new Set<string>();
  for (const edge of edges) {
    names.add(edge.source_character);
    names.add(edge.target_character);
  }

  const sorted = Array.from(names).sort((left, right) => left.localeCompare(right, "zh-CN"));
  const center = GRAPH_SIZE / 2;
  const radius = GRAPH_SIZE * 0.34;

  return sorted.map((name, index) => {
    const angle = (2 * Math.PI * index) / sorted.length - Math.PI / 2;
    return {
      id: name,
      label: name,
      x: center + radius * Math.cos(angle),
      y: center + radius * Math.sin(angle),
    };
  });
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

type RelationshipGraphProps = {
  edges: RelationshipEdge[];
};

export function RelationshipGraph({ edges }: RelationshipGraphProps) {
  const [activeEdgeId, setActiveEdgeId] = useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  const { edges: visibleEdges, hiddenCount } = useMemo(() => dedupeRelationshipEdges(edges), [edges]);
  const nodes = useMemo(() => buildNodes(visibleEdges), [visibleEdges]);
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

  return (
    <div className="relationship-graph">
      {hiddenCount > 0 ? (
        <p className="relationship-graph-dedupe-hint">
          已合并显示 {visibleEdges.length} 条关系，隐藏了 {hiddenCount} 条重复记录。可在 Agent 对话中清理重复数据。
        </p>
      ) : null}
      <svg
        aria-label="人物关系图谱"
        className="relationship-graph-canvas"
        role="img"
        viewBox={`0 0 ${GRAPH_SIZE} ${GRAPH_SIZE}`}
      >
        <defs>
          {Array.from(relationshipColors.entries()).map(([type, color], index) => (
            <marker
              id={`relationship-graph-arrow-${index}`}
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
                markerEnd={colorIndex >= 0 ? `url(#relationship-graph-arrow-${colorIndex})` : undefined}
                onClick={() => setActiveEdgeId(edge.id)}
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
                onClick={() => setActiveEdgeId(edge.id)}
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
              onMouseEnter={() => setHoveredNodeId(node.id)}
              onMouseLeave={() => setHoveredNodeId(null)}
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
          <p className="relationship-graph-detail-hint">点击关系连线或标签查看详情，悬停角色可高亮相关关系</p>
        )}
      </div>
    </div>
  );
}
