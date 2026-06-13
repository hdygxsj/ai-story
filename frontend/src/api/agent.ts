import { API_BASE, apiRequest } from "./http";
import type { WorkspaceNode } from "./workspace";

export type AgentConfirmation = {
  id: string;
  action_type: string;
  status: string;
  payload: Record<string, unknown>;
};

export type ContextDetailItem = {
  source: string;
  tokens: number;
  compressed: boolean;
};

export type ContextDetail = {
  usage_ratio: number;
  items: ContextDetailItem[];
  warnings: string[];
  snapshot_id?: string | null;
};

export type AgentMessageResponse = {
  message: string;
  context_status: string[];
  context_detail?: ContextDetail | null;
  conversation_id?: string | null;
  confirmation: AgentConfirmation | null;
  workspace_diff?: WorkspaceDiff | null;
  workspace_nodes?: WorkspaceNode[] | null;
};

export type WorkspaceDiffSnapshot = {
  id: string;
  title: string;
  parent_id: string | null;
  position: number;
  status: string;
};

export type WorkspaceDiffChange = {
  action: string;
  node_id: string;
  title: string;
  before_parent_id?: string | null;
  after_parent_id?: string | null;
  before_position?: number;
  after_position?: number;
};

export type WorkspaceDiff = {
  summary: string;
  before: WorkspaceDiffSnapshot[];
  after: WorkspaceDiffSnapshot[];
  changes: WorkspaceDiffChange[];
};

export function sendAgentMessage(
  token: string,
  novelId: string,
  payload: { message: string; document_id?: string | null; selected_text?: string | null },
) {
  return apiRequest<AgentMessageResponse>(`/novels/${novelId}/agent/messages`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export type AgentStreamDeltaPayload = {
  type: "delta";
  content: string;
};

export type AgentStreamDonePayload = AgentMessageResponse & {
  type: "done";
  proposed_payload?: Record<string, unknown> | null;
};

export type AgentStreamEvent = AgentStreamDeltaPayload | AgentStreamDonePayload;

export type AgentStreamHandlers = {
  onDelta: (content: string) => void;
  onDone: (payload: AgentStreamDonePayload) => void;
  onError: (error: Error) => void;
};

export async function streamAgentMessage(
  token: string,
  novelId: string,
  payload: {
    message: string;
    document_id?: string | null;
    selected_text?: string | null;
    conversation_id?: string | null;
  },
  handlers: AgentStreamHandlers,
) {
  const headers = new Headers({ "Content-Type": "application/json" });
  headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}/novels/${novelId}/agent/messages/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
  } catch (error) {
    handlers.onError(error instanceof Error ? error : new Error("Agent 流式请求失败"));
    return;
  }

  if (!response.ok) {
    handlers.onError(new Error(await response.text()));
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    handlers.onError(new Error("浏览器不支持流式响应"));
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  function parseSseEvent(event: string) {
    const line = event
      .split("\n")
      .map((part) => part.trim())
      .find((part) => part.startsWith("data: "));
    if (!line) {
      return;
    }
    const parsed = JSON.parse(line.slice(6)) as AgentStreamEvent;
    if (parsed.type === "delta") {
      handlers.onDelta(parsed.content);
      return;
    }
    handlers.onDone(parsed);
  }

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";
      for (const event of events) {
        parseSseEvent(event);
      }
    }
    buffer += decoder.decode();
    if (buffer.trim()) {
      parseSseEvent(buffer);
    }
  } catch (error) {
    handlers.onError(error instanceof Error ? error : new Error("Agent 流式响应解析失败"));
  }
}
