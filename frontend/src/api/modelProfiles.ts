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

export function listModelProfiles(token: string) {
  return apiRequest<ModelProfile[]>("/model-profiles", { token });
}
