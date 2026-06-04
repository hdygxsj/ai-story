import { apiRequest } from "./http";
import type { WorkspaceNode } from "./workspace";

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
