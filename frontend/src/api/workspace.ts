import { apiRequest } from "./http";

export type WorkspaceNode = {
  id: string;
  novel_id: string;
  parent_id: string | null;
  document_id: string | null;
  title: string;
  node_type: string;
  status: string;
  position: number;
};

export function listWorkspaceNodes(token: string, novelId: string) {
  return apiRequest<WorkspaceNode[]>(`/novels/${novelId}/nodes`, { token });
}

export function createWorkspaceNode(token: string, novelId: string, title: string, nodeType: string) {
  return apiRequest<WorkspaceNode>(`/novels/${novelId}/nodes`, {
    method: "POST",
    token,
    body: JSON.stringify({ title, node_type: nodeType, parent_id: null }),
  });
}
