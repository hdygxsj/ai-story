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
};

export type CharacterState = {
  id: string;
  character_name: string;
  state: string;
  scope?: string;
};

export type RelationshipEdge = {
  id: string;
  source_character: string;
  target_character: string;
  relationship_type: string;
  description?: string;
};

export function listCreativeAssets(token: string, novelId: string) {
  return apiRequest<CreativeAsset[]>(`/novels/${novelId}/creative-assets`, { token });
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
