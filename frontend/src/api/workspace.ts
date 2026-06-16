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

export type WorkspaceNodeReorderItem = {
  id: string;
  parent_id: string | null;
  position: number;
  title?: string;
  status?: string;
};

export function listWorkspaceNodes(token: string, novelId: string) {
  return apiRequest<WorkspaceNode[]>(`/novels/${novelId}/nodes`, { token });
}

export function createWorkspaceNode(
  token: string,
  novelId: string,
  title: string,
  nodeType: string,
  parentId: string | null = null,
) {
  return apiRequest<WorkspaceNode>(`/novels/${novelId}/nodes`, {
    method: "POST",
    token,
    body: JSON.stringify({ title, node_type: nodeType, parent_id: parentId }),
  });
}

export function updateWorkspaceNode(
  token: string,
  novelId: string,
  nodeId: string,
  payload: Partial<Pick<WorkspaceNode, "parent_id" | "position" | "title">>,
) {
  return apiRequest<WorkspaceNode>(`/novels/${novelId}/nodes/${nodeId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
  });
}

export function reorderWorkspaceNodes(token: string, novelId: string, items: WorkspaceNodeReorderItem[]) {
  return apiRequest<WorkspaceNode[]>(`/novels/${novelId}/nodes/reorder`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ items }),
  });
}

export function emptyWorkspaceTrash(token: string, novelId: string) {
  return apiRequest<{ deleted_count: number }>(`/novels/${novelId}/nodes/trash`, {
    method: "DELETE",
    token,
  });
}

export async function exportWorkspaceNode(
  token: string,
  novelId: string,
  nodeId: string,
  format: "markdown" | "txt",
) {
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE ?? "http://localhost:8000"}/novels/${novelId}/nodes/${nodeId}/export?format=${format}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.blob();
}
