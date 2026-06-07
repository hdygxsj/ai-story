import { apiRequest } from "./http";

export type ModelProfile = {
  id: string;
  name: string;
  provider_kind: string;
  base_url?: string | null;
  chat_provider_kind?: string | null;
  chat_base_url?: string | null;
  chat_model: string;
  writing_provider_kind?: string | null;
  writing_base_url?: string | null;
  writing_model: string;
  summary_provider_kind?: string | null;
  summary_base_url?: string | null;
  summary_model: string;
  embedding_provider_kind?: string | null;
  embedding_base_url?: string | null;
  embedding_model: string;
};

export type ModelProfileCreate = Omit<ModelProfile, "id" | "embedding_model"> & {
  embedding_model?: string;
  api_key: string;
  base_url?: string | null;
  chat_api_key?: string | null;
  embedding_api_key?: string | null;
  summary_api_key?: string | null;
  writing_api_key?: string | null;
  context_window?: number;
  embedding_dimensions?: number;
  supports_json_mode?: boolean;
  supports_streaming?: boolean;
  supports_tool_calling?: boolean;
};

export function listModelProfiles(token: string) {
  return apiRequest<ModelProfile[]>("/model-profiles", { token });
}

export type ModelProfileUpdate = Partial<ModelProfileCreate>;

export function createModelProfile(token: string, payload: ModelProfileCreate) {
  return apiRequest<ModelProfile>("/model-profiles", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function updateModelProfile(token: string, profileId: string, payload: ModelProfileUpdate) {
  return apiRequest<ModelProfile>(`/model-profiles/${profileId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
  });
}

export type ModelProfilePurpose = "chat" | "writing" | "summary" | "embedding";

export type ModelProfileConnectivityResult = {
  purpose: string;
  label: string;
  ok: boolean;
  message: string;
  model: string;
};

export type ModelProfileTestPayload = Partial<ModelProfileCreate> & {
  profile_id?: string | null;
  chat_model: string;
  embedding_model?: string;
  name: string;
  provider_kind: string;
  purposes?: ModelProfilePurpose[];
  summary_model: string;
  writing_model: string;
};

export function testModelProfileConnectivity(token: string, payload: ModelProfileTestPayload) {
  return apiRequest<{ results: ModelProfileConnectivityResult[] }>("/model-profiles/test-connectivity", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}
