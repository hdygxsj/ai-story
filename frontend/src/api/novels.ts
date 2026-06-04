import { apiRequest } from "./http";

export type Novel = {
  id: string;
  title: string;
  description: string;
  default_model_profile_id?: string | null;
};

export function listNovels(token: string) {
  return apiRequest<Novel[]>("/novels", { token });
}

export function createNovel(token: string, title: string) {
  return apiRequest<Novel>("/novels", {
    method: "POST",
    token,
    body: JSON.stringify({ title }),
  });
}

export function importNovel(token: string, payload: { title: string; content: string; format: "markdown" | "txt" }) {
  return apiRequest<Novel>("/novels/import", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function updateNovel(token: string, novelId: string, payload: Partial<Pick<Novel, "default_model_profile_id">>) {
  return apiRequest<Novel>(`/novels/${novelId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
  });
}

export async function exportNovel(token: string, novelId: string, format: "markdown" | "txt") {
  const response = await fetch(`${import.meta.env.VITE_API_BASE ?? "http://localhost:8000"}/novels/${novelId}/export?format=${format}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.blob();
}
