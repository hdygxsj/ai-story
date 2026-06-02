import { apiRequest } from "./http";

export type MemoryReviewItem = {
  id: string;
  memory_type: string;
  title: string;
  body: string;
  importance: number;
  status: string;
};

export type MemoryItem = Omit<MemoryReviewItem, "status">;

export function listMemoryReviewItems(token: string, novelId: string) {
  return apiRequest<MemoryReviewItem[]>(`/novels/${novelId}/memory-review-items`, { token });
}

export function createMemoryReviewItem(
  token: string,
  novelId: string,
  payload: Omit<MemoryReviewItem, "id" | "status">,
) {
  return apiRequest<MemoryReviewItem>(`/novels/${novelId}/memory-review-items`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function approveMemoryReviewItem(token: string, itemId: string) {
  return apiRequest<MemoryItem>(`/memory-review-items/${itemId}/approve`, {
    method: "POST",
    token,
  });
}

export function rejectMemoryReviewItem(token: string, itemId: string) {
  return apiRequest<MemoryReviewItem>(`/memory-review-items/${itemId}/reject`, {
    method: "POST",
    token,
  });
}

export function listMemoryItems(token: string, novelId: string) {
  return apiRequest<MemoryItem[]>(`/novels/${novelId}/memory-items`, { token });
}
