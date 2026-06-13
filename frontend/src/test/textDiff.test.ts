import { describe, expect, it } from "vitest";

import { diffText, hasDiffChanges, toDisplaySegments } from "../features/confirmations/textDiff";

describe("textDiff", () => {
  it("marks adjacent delete and insert as modify", () => {
    const segments = toDisplaySegments([
      { type: "delete", value: "旧段落" },
      { type: "insert", value: "新段落" },
    ]);

    expect(segments).toEqual([{ kind: "modify", before: "旧段落", after: "新段落" }]);
  });

  it("detects insert and delete blocks in multi-line text", () => {
    const segments = diffText("第一段\n\n第二段", "第一段\n\n第二段改\n\n第三段");

    expect(hasDiffChanges(segments)).toBe(true);
    expect(segments.some((segment) => segment.kind === "insert" || segment.kind === "modify")).toBe(true);
  });
});
