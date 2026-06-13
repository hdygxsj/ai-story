import { describe, expect, it } from "vitest";

import type { Conversation } from "../api/conversations";
import {
  formatConversationTime,
  getConversationSubtitle,
  getConversationTooltip,
} from "../features/agent/conversationPresentation";

function buildConversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: "conv-1",
    novel_id: "novel-1",
    title: "帮我整理第三章大纲",
    created_at: "2026-06-14T10:00:00.000Z",
    updated_at: "2026-06-14T12:30:00.000Z",
    message_count: 2,
    preview: "好的，我来帮你整理。",
    ...overrides,
  };
}

describe("conversationPresentation", () => {
  it("formats conversation time for display", () => {
    expect(formatConversationTime("2026-06-14T12:30:00.000Z")).toMatch(/\d/);
  });

  it("shows preview or empty-state subtitle", () => {
    expect(getConversationSubtitle(buildConversation())).toBe("好的，我来帮你整理。");
    expect(getConversationSubtitle(buildConversation({ preview: null, message_count: 0 }))).toBe("尚未开始对话");
  });

  it("builds tooltip from title and time", () => {
    const tooltip = getConversationTooltip(buildConversation());
    expect(tooltip.startsWith("帮我整理第三章大纲 · ")).toBe(true);
  });
});
