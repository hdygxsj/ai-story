import { apiRequest } from "./http";

export type DocumentBody = Record<string, unknown>;

export type DocumentRecord = {
  id: string;
  novel_id: string;
  content: DocumentBody;
};

export type DocumentVersion = {
  id: string;
  document_id: string;
  source: string;
  content: DocumentBody;
  created_at: string;
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

export function listDocumentVersions(token: string, documentId: string) {
  return apiRequest<DocumentVersion[]>(`/documents/${documentId}/versions`, { token });
}

export function restoreDocumentVersion(token: string, documentId: string, versionId: string) {
  return apiRequest<DocumentRecord>(`/documents/${documentId}/versions/${versionId}/restore`, {
    method: "POST",
    token,
  });
}
