import { describe, expect, it } from "vitest";

import { expandStoredConversationMessages } from "../features/agent/agentMessages";

describe("expandStoredConversationMessages", () => {
  it("splits stored assistant messages into separate tool and text bubbles", () => {
    const expanded = expandStoredConversationMessages([
      {
        id: "user-1",
        role: "user",
        content: "写第一章",
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "assistant-1",
        role: "assistant",
        content: "第一章已写入。",
        created_at: "2026-01-01T00:00:01Z",
        metadata: {
          tool_calls: [
            {
              id: "run-1",
              tool: "create_chapter_with_content",
              status: "ok",
              summary: "已将《第一章》写入工作台。",
            },
          ],
        },
      },
    ]);

    expect(expanded).toHaveLength(3);
    expect(expanded[0]).toMatchObject({ role: "user", content: "写第一章" });
    expect(expanded[1]).toMatchObject({
      role: "tool",
      toolCall: { id: "run-1", tool: "create_chapter_with_content" },
    });
    expect(expanded[2]).toMatchObject({ role: "assistant", content: "第一章已写入。" });
  });
});
