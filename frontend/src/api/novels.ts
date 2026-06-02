import { apiRequest } from "./http";

export type Novel = {
  id: string;
  title: string;
  description: string;
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
