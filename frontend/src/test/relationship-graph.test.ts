import { describe, expect, it } from "vitest";

import { dedupeRelationshipEdges } from "../features/workspace/RelationshipGraph";

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
