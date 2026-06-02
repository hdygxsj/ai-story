import { apiRequest } from "./http";

export type MemoryReviewItem = {
  id: string;
  memory_type: string;
  title: string;
  body: string;
  importance: number;
  status: string;
};

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
