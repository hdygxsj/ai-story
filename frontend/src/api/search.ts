import { apiRequest } from "./http";

export type DocumentSearchHit = {
  document_id: string;
  node_id: string;
  node_title: string;
  match_index: number;
  match_length: number;
  matched_text: string;
  snippet: string;
  match_source: "body" | "title";
  total_matches_in_document: number;
  occurrence_index?: number | null;
};

export function searchNovelDocuments(token: string, novelId: string, query: string, limit = 50) {
  const params = new URLSearchParams({ query, limit: String(limit) });
  return apiRequest<DocumentSearchHit[]>(`/novels/${novelId}/search?${params.toString()}`, { token });
}
