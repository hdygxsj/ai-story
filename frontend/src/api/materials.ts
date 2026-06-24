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

export type CharacterAttribute = {
  id: string;
  character_name: string;
  attribute_key: string;
  value: unknown;
  unit?: string;
  scope?: string;
  metadata?: Record<string, unknown>;
  created_at?: string;
};

export type CharacterAttributePayload = {
  character_name: string;
  attribute_key: string;
  value: unknown;
  unit?: string;
  scope?: string;
  metadata?: Record<string, unknown>;
};

export type InventoryItem = {
  id: string;
  owner_name: string;
  item_name: string;
  quantity: number;
  unit?: string;
  location_name?: string | null;
  description?: string;
  metadata?: Record<string, unknown>;
  created_at?: string;
};

export type InventoryItemPayload = {
  owner_name: string;
  item_name: string;
  quantity: number;
  unit?: string;
  location_name?: string | null;
  description?: string;
  metadata?: Record<string, unknown>;
};

export type MapLocation = {
  id: string;
  name: string;
  location_type: string;
  summary: string;
  parent_name?: string | null;
  coordinates?: Record<string, unknown>;
  adjacent_location_names?: string[];
  metadata?: Record<string, unknown>;
  created_at?: string;
};

export type MapLocationPayload = {
  name: string;
  location_type?: string;
  summary: string;
  parent_name?: string | null;
  coordinates?: Record<string, unknown>;
  adjacent_location_names?: string[];
  metadata?: Record<string, unknown>;
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

export function listCharacterAttributes(token: string, novelId: string) {
  return apiRequest<CharacterAttribute[]>(`/novels/${novelId}/character-attributes`, { token });
}

export function upsertCharacterAttribute(token: string, novelId: string, payload: CharacterAttributePayload) {
  return apiRequest<CharacterAttribute>(`/novels/${novelId}/character-attributes`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function updateCharacterAttribute(
  token: string,
  novelId: string,
  attributeId: string,
  payload: Partial<CharacterAttributePayload>,
) {
  return apiRequest<CharacterAttribute>(`/novels/${novelId}/character-attributes/${attributeId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
  });
}

export function deleteCharacterAttribute(token: string, novelId: string, attributeId: string) {
  return apiRequest<void>(`/novels/${novelId}/character-attributes/${attributeId}`, {
    method: "DELETE",
    token,
  });
}

export function listInventoryItems(token: string, novelId: string) {
  return apiRequest<InventoryItem[]>(`/novels/${novelId}/inventory-items`, { token });
}

export function upsertInventoryItem(token: string, novelId: string, payload: InventoryItemPayload) {
  return apiRequest<InventoryItem>(`/novels/${novelId}/inventory-items`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function updateInventoryItem(
  token: string,
  novelId: string,
  itemId: string,
  payload: Partial<InventoryItemPayload>,
) {
  return apiRequest<InventoryItem>(`/novels/${novelId}/inventory-items/${itemId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
  });
}

export function deleteInventoryItem(token: string, novelId: string, itemId: string) {
  return apiRequest<void>(`/novels/${novelId}/inventory-items/${itemId}`, {
    method: "DELETE",
    token,
  });
}

export function listMapLocations(token: string, novelId: string) {
  return apiRequest<MapLocation[]>(`/novels/${novelId}/map-locations`, { token });
}

export function upsertMapLocation(token: string, novelId: string, payload: MapLocationPayload) {
  return apiRequest<MapLocation>(`/novels/${novelId}/map-locations`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function updateMapLocation(
  token: string,
  novelId: string,
  locationId: string,
  payload: Partial<MapLocationPayload>,
) {
  return apiRequest<MapLocation>(`/novels/${novelId}/map-locations/${locationId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
  });
}

export function deleteMapLocation(token: string, novelId: string, locationId: string) {
  return apiRequest<void>(`/novels/${novelId}/map-locations/${locationId}`, {
    method: "DELETE",
    token,
  });
}

export function listRelationshipEdges(token: string, novelId: string) {
  return apiRequest<RelationshipEdge[]>(`/novels/${novelId}/relationship-edges`, { token });
}
