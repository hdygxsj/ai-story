import { apiRequest } from "./http";

export type Conversation = {
  id: string;
  novel_id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type StoredMessage = {
  id: string;
  role: string;
  content: string;
  created_at: string;
};

export function listConversations(token: string, novelId: string) {
  return apiRequest<Conversation[]>(`/novels/${novelId}/conversations`, { token });
}

export function createConversation(token: string, novelId: string, title?: string) {
  return apiRequest<Conversation>(`/novels/${novelId}/conversations`, {
    method: "POST",
    token,
    body: JSON.stringify({ title }),
  });
}

export function listConversationMessages(token: string, novelId: string, conversationId: string) {
  return apiRequest<StoredMessage[]>(`/novels/${novelId}/conversations/${conversationId}/messages`, { token });
}

export function updateConversation(token: string, novelId: string, conversationId: string, title: string) {
  return apiRequest<Conversation>(`/novels/${novelId}/conversations/${conversationId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ title }),
  });
}

export function deleteConversation(token: string, novelId: string, conversationId: string) {
  return apiRequest<void>(`/novels/${novelId}/conversations/${conversationId}`, {
    method: "DELETE",
    token,
  });
}

export type ContextSources = {
  current_document: boolean;
  selected_text: boolean;
  key_memories: boolean;
  structured_assets: boolean;
  neighboring_chapters: boolean;
  rag_search: boolean;
  conversation_history: boolean;
};

export type ContextBudgetSettings = {
  max_context_tokens: number;
  response_reserve: number;
  recent_chapters_count: number;
  conversation_history_limit: number;
};

export type ContextSettings = {
  novel_id: string;
  sources: ContextSources;
  budget: ContextBudgetSettings;
  updated_at: string;
};

export function getContextSettings(token: string, novelId: string) {
  return apiRequest<ContextSettings>(`/novels/${novelId}/context-settings`, { token });
}

export function updateContextSettings(
  token: string,
  novelId: string,
  payload: { sources?: ContextSources; budget?: ContextBudgetSettings },
) {
  return apiRequest<ContextSettings>(`/novels/${novelId}/context-settings`, {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
  });
}
