import { apiRequest } from "./http";

export type ModelProfile = {
  id: string;
  name: string;
  provider_kind: string;
  chat_model: string;
  writing_model: string;
  summary_model: string;
  embedding_model: string;
};

export type ModelProfileCreate = Omit<ModelProfile, "id"> & {
  api_key: string;
  base_url?: string | null;
  context_window?: number;
  embedding_dimensions?: number;
  supports_json_mode?: boolean;
  supports_streaming?: boolean;
  supports_tool_calling?: boolean;
};

export function listModelProfiles(token: string) {
  return apiRequest<ModelProfile[]>("/model-profiles", { token });
}

export function createModelProfile(token: string, payload: ModelProfileCreate) {
  return apiRequest<ModelProfile>("/model-profiles", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}
