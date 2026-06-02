import { apiRequest } from "./http";

export type DocumentBody = Record<string, unknown>;

export type DocumentRecord = {
  id: string;
  novel_id: string;
  content: DocumentBody;
};

export function getDocument(token: string, documentId: string) {
  return apiRequest<DocumentRecord>(`/documents/${documentId}`, { token });
}

export function updateDocument(token: string, documentId: string, content: DocumentBody) {
  return apiRequest<DocumentRecord>(`/documents/${documentId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ content }),
  });
}
