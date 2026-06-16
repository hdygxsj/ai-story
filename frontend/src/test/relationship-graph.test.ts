import { describe, expect, it } from "vitest";

import { dedupeRelationshipEdges } from "../features/workspace/RelationshipGraph";
import { buildRelationshipNetworkNodes } from "../features/workspace/relationshipGraphLayout";

describe("dedupeRelationshipEdges", () => {
  it("keeps one edge per source-target-type combination", () => {
    const result = dedupeRelationshipEdges([
      {
        id: "edge-1",
        source_character: "苏念",
        target_character: "叶尘",
        relationship_type: "恋人/守护",
        description: "旧说明",
      },
      {
        id: "edge-2",
        source_character: "苏念",
        target_character: "叶尘",
        relationship_type: "恋人/守护",
        description: "更完整的说明",
      },
      {
        id: "edge-3",
        source_character: "叶尘",
        target_character: "王磊",
        relationship_type: "挚友/生死兄弟",
        description: "",
      },
    ]);

    expect(result.hiddenCount).toBe(1);
    expect(result.edges).toHaveLength(2);
    expect(result.edges.find((edge) => edge.id === "edge-2")?.description).toBe("更完整的说明");
  });
});

describe("buildRelationshipNetworkNodes", () => {
  it("expands a dense relationship set into a stable network instead of a flat ring", () => {
    const nodes = buildRelationshipNetworkNodes([
      edge("1", "叶尘", "苏念"),
      edge("2", "叶尘", "王磊"),
      edge("3", "叶尘", "袁晓乐"),
      edge("4", "叶尘", "江若溪"),
      edge("5", "苏念", "秦上士"),
      edge("6", "江若溪", "江浩"),
      edge("7", "袁晓乐", "赵铁"),
    ]);

    const byId = new Map(nodes.map((node) => [node.id, node]));
    const center = byId.get("叶尘")!;
    const leaf = byId.get("秦上士")!;

    expect(nodes.map((node) => node.id)).toEqual([
      "叶尘",
      "江若溪",
      "苏念",
      "袁晓乐",
      "王磊",
      "江浩",
      "秦上士",
      "赵铁",
    ]);
    expect(distanceFromCenter(center)).toBeLessThan(96);
    expect(distanceFromCenter(leaf)).toBeGreaterThan(190);
  });
});

function edge(id: string, source: string, target: string) {
  return {
    id,
    source_character: source,
    target_character: target,
    relationship_type: "关系",
    description: "",
  };
}

function distanceFromCenter(node: { x: number; y: number }) {
  return Math.hypot(node.x - 260, node.y - 260);
}
