import type { AgentToolCallRecord } from "../../api/agent";
import type { StoredMessage } from "../../api/conversations";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  toolCall?: AgentToolCallRecord;
};

export function createMessageId(role: ChatMessage["role"]) {
  return `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function expandStoredConversationMessages(stored: StoredMessage[]): ChatMessage[] {
  const expanded: ChatMessage[] = [];

  for (const item of stored) {
    if (item.role === "user") {
      expanded.push({
        id: item.id,
        role: "user",
        content: item.content,
      });
      continue;
    }

    for (const toolCall of item.metadata?.tool_calls ?? []) {
      expanded.push({
        id: `${item.id}-tool-${toolCall.id}`,
        role: "tool",
        content: "",
        toolCall,
      });
    }

    if (item.content.trim()) {
      expanded.push({
        id: item.id,
        role: "assistant",
        content: item.content,
      });
    }
  }

  return expanded;
}

export function removeEmptyAssistantMessages(messages: ChatMessage[], assistantId: string) {
  return messages.filter((item) => {
    if (item.id !== assistantId) {
      return true;
    }
    return item.role === "assistant" && item.content.trim().length > 0;
  });
}
