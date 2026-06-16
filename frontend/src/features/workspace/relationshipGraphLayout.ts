import type { RelationshipEdge } from "../../api/materials";
import { GRAPH_SIZE } from "./relationshipGraphView";

export type GraphNode = {
  id: string;
  label: string;
  x: number;
  y: number;
};

type NodeStats = {
  degree: number;
  firstSeen: number;
  id: string;
  neighbors: Set<string>;
};

const CENTER = GRAPH_SIZE / 2;
const INNER_RADIUS = GRAPH_SIZE * 0.27;
const MIDDLE_RADIUS = GRAPH_SIZE * 0.36;
const OUTER_RADIUS = GRAPH_SIZE * 0.44;

export function buildRelationshipNetworkNodes(edges: RelationshipEdge[]): GraphNode[] {
  const stats = buildNodeStats(edges);
  const ranked = Array.from(stats.values()).sort(compareByNetworkImportance);

  if (ranked.length === 0) {
    return [];
  }

  const coreCount = Math.min(ranked.length, Math.max(1, Math.ceil(Math.sqrt(ranked.length)) + 1));
  const coreNodes = ranked.slice(0, coreCount);
  const coreIds = new Set(coreNodes.map((node) => node.id));
  const coreAngles = buildCoreAngles(coreNodes);
  const positioned = new Map<string, GraphNode>();
  const layoutOrder: string[] = coreNodes.map((node) => node.id);

  coreNodes.forEach((node, index) => {
    if (index === 0) {
      positioned.set(node.id, nodeAt(node.id, CENTER, CENTER));
      return;
    }

    const angle = coreAngles.get(node.id) ?? 0;
    const radius = index <= 4 ? INNER_RADIUS : MIDDLE_RADIUS;
    positioned.set(node.id, nodeFromPolar(node.id, angle, radius));
  });

  const branchGroups = new Map<string, NodeStats[]>();
  for (const node of ranked.slice(coreCount)) {
    const anchor = chooseAnchor(node, coreNodes, stats, coreIds);
    const group = branchGroups.get(anchor.id) ?? [];
    group.push(node);
    branchGroups.set(anchor.id, group);
  }

  for (const anchor of coreNodes) {
    const group = branchGroups.get(anchor.id);
    if (!group) {
      continue;
    }

    const anchorAngle = coreAngles.get(anchor.id) ?? -Math.PI / 2;
    const orderedGroup = group.sort(compareByNetworkImportance);
    const spread = Math.min(Math.PI * 0.42, Math.max(Math.PI * 0.14, orderedGroup.length * 0.11));

    orderedGroup.forEach((node, index) => {
      const ratio = orderedGroup.length === 1 ? 0.5 : index / (orderedGroup.length - 1);
      const angle = anchorAngle - spread / 2 + spread * ratio;
      const radius = node.neighbors.size > 1 ? MIDDLE_RADIUS : OUTER_RADIUS;
      positioned.set(node.id, nodeFromPolar(node.id, angle, radius));
      layoutOrder.push(node.id);
    });
  }

  return layoutOrder.map((id) => positioned.get(id) ?? nodeAt(id, CENTER, CENTER));
}

function buildNodeStats(edges: RelationshipEdge[]): Map<string, NodeStats> {
  const stats = new Map<string, NodeStats>();

  edges.forEach((edge, index) => {
    const source = ensureNodeStats(stats, edge.source_character, index);
    const target = ensureNodeStats(stats, edge.target_character, index);

    source.degree += 1;
    target.degree += 1;
    source.neighbors.add(target.id);
    target.neighbors.add(source.id);
  });

  return stats;
}

function ensureNodeStats(stats: Map<string, NodeStats>, id: string, firstSeen: number): NodeStats {
  const existing = stats.get(id);
  if (existing) {
    return existing;
  }

  const node = {
    degree: 0,
    firstSeen,
    id,
    neighbors: new Set<string>(),
  };
  stats.set(id, node);
  return node;
}

function buildCoreAngles(coreNodes: NodeStats[]): Map<string, number> {
  const angles = new Map<string, number>();

  if (coreNodes.length === 1) {
    angles.set(coreNodes[0]!.id, -Math.PI / 2);
    return angles;
  }

  coreNodes.forEach((node, index) => {
    if (index === 0) {
      angles.set(node.id, -Math.PI / 2);
      return;
    }

    const ringIndex = index - 1;
    const ringTotal = coreNodes.length - 1;
    angles.set(node.id, (2 * Math.PI * ringIndex) / ringTotal - Math.PI / 2);
  });

  return angles;
}

function chooseAnchor(
  node: NodeStats,
  coreNodes: NodeStats[],
  stats: Map<string, NodeStats>,
  coreIds: Set<string>,
): NodeStats {
  const coreNeighbors = Array.from(node.neighbors)
    .filter((neighbor) => coreIds.has(neighbor))
    .map((neighbor) => stats.get(neighbor))
    .filter((neighbor): neighbor is NodeStats => Boolean(neighbor))
    .sort(compareByNetworkImportance);

  return coreNeighbors[0] ?? coreNodes[0]!;
}

function compareByNetworkImportance(left: NodeStats, right: NodeStats): number {
  return (
    right.degree - left.degree ||
    left.id.localeCompare(right.id, "zh-CN") ||
    left.firstSeen - right.firstSeen
  );
}

function nodeFromPolar(id: string, angle: number, radius: number): GraphNode {
  return nodeAt(id, CENTER + radius * Math.cos(angle), CENTER + radius * Math.sin(angle));
}

function nodeAt(id: string, x: number, y: number): GraphNode {
  return {
    id,
    label: id,
    x,
    y,
  };
}
