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

type PlacementIntent = {
  angle: number;
  id: string;
  radius: number;
};

const CENTER = GRAPH_SIZE / 2;
const INNER_RADIUS = GRAPH_SIZE * 0.24;
const MIDDLE_RADIUS = GRAPH_SIZE * 0.35;
const OUTER_RADIUS = GRAPH_SIZE * 0.44;
const MIN_NODE_DISTANCE = 92;

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
  const intents: PlacementIntent[] = [];
  const layoutOrder: string[] = coreNodes.map((node) => node.id);

  coreNodes.forEach((node, index) => {
    if (index === 0) {
      intents.push({ id: node.id, angle: -Math.PI / 2, radius: 0 });
      return;
    }

    const angle = coreAngles.get(node.id) ?? 0;
    const radius = index <= 4 ? INNER_RADIUS : MIDDLE_RADIUS;
    intents.push({ id: node.id, angle, radius });
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
      intents.push({ id: node.id, angle, radius });
      layoutOrder.push(node.id);
    });
  }

  const positioned = resolveReadablePositions(intents);
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

function resolveReadablePositions(intents: PlacementIntent[]): Map<string, GraphNode> {
  const positioned = new Map<string, GraphNode>();
  const slots = buildReadableSlots(Math.max(0, intents.length - 1));

  for (const intent of intents) {
    if (intent.radius === 0) {
      positioned.set(intent.id, nodeAt(intent.id, CENTER, CENTER));
      continue;
    }

    const slot = chooseReadableSlot(intent, slots, Array.from(positioned.values()));
    positioned.set(intent.id, nodeFromPolar(intent.id, slot.angle, slot.radius));
  }

  return positioned;
}

function buildReadableSlots(nodeCount: number): Array<{ angle: number; radius: number }> {
  const slots: Array<{ angle: number; radius: number }> = [];
  const ringSpecs = [
    { count: 6, radius: INNER_RADIUS },
    { count: 10, radius: MIDDLE_RADIUS },
    { count: 14, radius: OUTER_RADIUS },
  ];

  for (const ring of ringSpecs) {
    for (let index = 0; index < ring.count; index += 1) {
      slots.push({
        angle: (2 * Math.PI * index) / ring.count - Math.PI / 2,
        radius: ring.radius,
      });
    }
  }

  if (nodeCount <= slots.length) {
    return slots;
  }

  const extraCount = nodeCount - slots.length;
  for (let index = 0; index < extraCount; index += 1) {
    slots.push({
      angle: (2 * Math.PI * index) / Math.max(extraCount, 1) - Math.PI / 2,
      radius: OUTER_RADIUS,
    });
  }

  return slots;
}

function chooseReadableSlot(
  intent: PlacementIntent,
  slots: Array<{ angle: number; radius: number }>,
  existingNodes: GraphNode[],
): { angle: number; radius: number } {
  const candidates = slots
    .filter((slot) => isReadableSlot(slot, existingNodes))
    .sort((left, right) => slotScore(left, intent) - slotScore(right, intent));

  const slot = candidates[0] ?? slots.sort((left, right) => slotScore(left, intent) - slotScore(right, intent))[0];
  slots.splice(slots.indexOf(slot!), 1);
  return slot!;
}

function isReadableSlot(slot: { angle: number; radius: number }, existingNodes: GraphNode[]): boolean {
  const x = CENTER + slot.radius * Math.cos(slot.angle);
  const y = CENTER + slot.radius * Math.sin(slot.angle);
  return existingNodes.every((node) => Math.hypot(node.x - x, node.y - y) >= MIN_NODE_DISTANCE);
}

function slotScore(slot: { angle: number; radius: number }, intent: PlacementIntent): number {
  return angleDistance(slot.angle, intent.angle) * 120 + Math.abs(slot.radius - intent.radius);
}

function angleDistance(left: number, right: number): number {
  const delta = Math.abs(left - right) % (2 * Math.PI);
  return Math.min(delta, 2 * Math.PI - delta);
}

function nodeAt(id: string, x: number, y: number): GraphNode {
  return {
    id,
    label: id,
    x,
    y,
  };
}
