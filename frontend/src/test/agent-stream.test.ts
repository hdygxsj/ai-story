import { describe, expect, it, vi } from "vitest";

import { parseAgentSseEvent } from "../api/agent";

describe("parseAgentSseEvent", () => {
  it("dispatches stream metadata before the final done event", () => {
    const onMeta = vi.fn();

    parseAgentSseEvent('data: {"type":"meta","conversation_id":"conversation-1"}', {
      onDelta: vi.fn(),
      onToolCall: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
      onMeta,
    });

    expect(onMeta).toHaveBeenCalledWith({ conversation_id: "conversation-1" });
  });
});
