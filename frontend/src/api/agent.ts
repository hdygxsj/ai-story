import { apiRequest } from "./http";

export type AgentConfirmation = {
  id: string;
  action_type: string;
  status: string;
  payload: Record<string, unknown>;
};

export type AgentMessageResponse = {
  message: string;
  context_status: string[];
  confirmation: AgentConfirmation | null;
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
