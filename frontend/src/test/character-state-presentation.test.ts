import { describe, expect, it } from "vitest";

import { dedupeCharacterStates } from "../features/workspace/characterStatePresentation";

describe("dedupeCharacterStates", () => {
  it("keeps the latest record for the same character and scope", () => {
    const deduped = dedupeCharacterStates([
      {
        id: "old",
        character_name: "叶尘",
        state: "【开局状态】",
        scope: "current",
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "new",
        character_name: "叶尘",
        state: "【第三章末】",
        scope: "current",
        created_at: "2026-01-02T00:00:00Z",
      },
      {
        id: "other",
        character_name: "王磊",
        state: "室友",
        scope: "current",
        created_at: "2026-01-03T00:00:00Z",
      },
    ]);

    expect(deduped).toHaveLength(2);
    expect(deduped.find((item) => item.character_name === "叶尘")?.id).toBe("new");
  });
});
