import { apiRequest } from "./http";

export type CreativeAsset = {
  id: string;
  asset_type: string;
  name: string;
  summary: string;
};

export type TimelineEvent = {
  id: string;
  title: string;
  event_time: string;
  summary?: string;
  position?: number | null;
  created_at?: string;
};

export type CharacterState = {
  id: string;
  character_name: string;
  state: string;
  scope?: string;
  created_at?: string;
};

export type RelationshipEdge = {
  id: string;
  source_character: string;
  target_character: string;
  relationship_type: string;
  description?: string;
  metadata?: Record<string, unknown>;
  created_at?: string;
};

export type MaterialChange = {
  id: string;
  material_type: string;
  material_id: string;
  action: "created" | "updated" | "deleted";
  actor_source: "user" | "agent";
  summary: string;
  before_data?: Record<string, unknown> | null;
  after_data?: Record<string, unknown> | null;
  created_at: string;
};

export function listCreativeAssets(token: string, novelId: string) {
  return apiRequest<CreativeAsset[]>(`/novels/${novelId}/creative-assets`, { token });
}

export function updateCreativeAsset(
  token: string,
  novelId: string,
  assetId: string,
  payload: Partial<Pick<CreativeAsset, "asset_type" | "name" | "summary">>,
) {
  return apiRequest<CreativeAsset>(`/novels/${novelId}/creative-assets/${assetId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
  });
}

export function deleteCreativeAsset(token: string, novelId: string, assetId: string) {
  return apiRequest<void>(`/novels/${novelId}/creative-assets/${assetId}`, {
    method: "DELETE",
    token,
  });
}

export function listMaterialChanges(
  token: string,
  novelId: string,
  params?: { material_type?: string; material_id?: string; limit?: number },
) {
  const search = new URLSearchParams();
  if (params?.material_type) {
    search.set("material_type", params.material_type);
  }
  if (params?.material_id) {
    search.set("material_id", params.material_id);
  }
  if (params?.limit) {
    search.set("limit", String(params.limit));
  }
  const query = search.toString();
  return apiRequest<MaterialChange[]>(`/novels/${novelId}/material-changes${query ? `?${query}` : ""}`, { token });
}

export function listTimelineEvents(token: string, novelId: string) {
  return apiRequest<TimelineEvent[]>(`/novels/${novelId}/timeline-events`, { token });
}

export function listCharacterStates(token: string, novelId: string) {
  return apiRequest<CharacterState[]>(`/novels/${novelId}/character-states`, { token });
}

export function listRelationshipEdges(token: string, novelId: string) {
  return apiRequest<RelationshipEdge[]>(`/novels/${novelId}/relationship-edges`, { token });
}
