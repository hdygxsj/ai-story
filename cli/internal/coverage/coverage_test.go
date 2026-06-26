package coverage_test

import (
	"testing"

	"aistorycli/internal/coverage"
)

func TestRoutesIncludeCurrentBackendSurface(t *testing.T) {
	want := []string{
		"POST /auth/register",
		"POST /auth/login",
		"GET /auth/me",
		"POST /model-profiles",
		"GET /model-profiles",
		"PATCH /model-profiles/{profile_id}",
		"DELETE /model-profiles/{profile_id}",
		"POST /model-profiles/test-connectivity",
		"POST /novels",
		"POST /novels/import",
		"GET /novels",
		"PATCH /novels/{novel_id}",
		"GET /novels/{novel_id}/export",
		"GET /novels/{novel_id}/nodes/{node_id}/export",
		"POST /novels/{novel_id}/nodes",
		"GET /novels/{novel_id}/nodes",
		"DELETE /novels/{novel_id}/nodes/trash",
		"PATCH /novels/{novel_id}/nodes/reorder",
		"PATCH /novels/{novel_id}/nodes/{node_id}",
		"GET /documents/{document_id}",
		"PATCH /documents/{document_id}",
		"GET /documents/{document_id}/versions",
		"POST /documents/{document_id}/versions/{version_id}/restore",
		"GET /novels/{novel_id}/confirmations",
		"GET /novels/{novel_id}/confirmations/history",
		"POST /confirmations/{confirmation_id}/approve",
		"POST /confirmations/{confirmation_id}/reject",
		"GET /novels/{novel_id}/conversations",
		"POST /novels/{novel_id}/conversations",
		"GET /novels/{novel_id}/conversations/{conversation_id}",
		"PATCH /novels/{novel_id}/conversations/{conversation_id}",
		"DELETE /novels/{novel_id}/conversations/{conversation_id}",
		"GET /novels/{novel_id}/conversations/{conversation_id}/messages",
		"GET /novels/{novel_id}/context-settings",
		"PATCH /novels/{novel_id}/context-settings",
		"POST /novels/{novel_id}/memory-review-items",
		"GET /novels/{novel_id}/memory-review-items",
		"POST /memory-review-items/{item_id}/approve",
		"POST /memory-review-items/{item_id}/reject",
		"GET /novels/{novel_id}/memory-items",
		"POST /novels/{novel_id}/memory-items",
		"DELETE /memory-items/{item_id}",
		"POST /novels/{novel_id}/creative-assets",
		"GET /novels/{novel_id}/creative-assets",
		"PATCH /novels/{novel_id}/creative-assets/{asset_id}",
		"DELETE /novels/{novel_id}/creative-assets/{asset_id}",
		"POST /novels/{novel_id}/timeline-events",
		"GET /novels/{novel_id}/timeline-events",
		"PATCH /novels/{novel_id}/timeline-events/{event_id}",
		"POST /novels/{novel_id}/timeline-events/reorder",
		"DELETE /novels/{novel_id}/timeline-events/{event_id}",
		"POST /novels/{novel_id}/character-states",
		"GET /novels/{novel_id}/character-states",
		"PATCH /novels/{novel_id}/character-states/{state_id}",
		"DELETE /novels/{novel_id}/character-states/{state_id}",
		"POST /novels/{novel_id}/character-attributes",
		"GET /novels/{novel_id}/character-attributes",
		"PATCH /novels/{novel_id}/character-attributes/{attribute_id}",
		"DELETE /novels/{novel_id}/character-attributes/{attribute_id}",
		"POST /novels/{novel_id}/inventory-items",
		"GET /novels/{novel_id}/inventory-items",
		"PATCH /novels/{novel_id}/inventory-items/{item_id}",
		"DELETE /novels/{novel_id}/inventory-items/{item_id}",
		"POST /novels/{novel_id}/map-locations",
		"GET /novels/{novel_id}/map-locations",
		"PATCH /novels/{novel_id}/map-locations/{location_id}",
		"DELETE /novels/{novel_id}/map-locations/{location_id}",
		"POST /novels/{novel_id}/relationship-edges",
		"GET /novels/{novel_id}/relationship-edges",
		"PATCH /novels/{novel_id}/relationship-edges/{edge_id}",
		"DELETE /novels/{novel_id}/relationship-edges/{edge_id}",
		"GET /novels/{novel_id}/material-changes",
		"GET /novels/{novel_id}/rag/search",
		"GET /novels/{novel_id}/search",
		"POST /novels/{novel_id}/agent/messages",
		"POST /novels/{novel_id}/agent/messages/stream",
		"GET /local-agent-skill/SKILL.md",
		"GET /local-scoring-skill/SKILL.md",
		"GET /agent-tools",
		"GET /agent-tools/{tool_name}",
		"POST /novels/{novel_id}/agent/tools/{tool_name}",
	}
	got := coverage.RouteKeys()
	for _, key := range want {
		if !got[key] {
			t.Fatalf("missing route coverage: %s", key)
		}
	}
}

func TestAgentToolsIncludeCurrentRuntimeSurface(t *testing.T) {
	want := []string{
		"read_document", "search_memory", "search_rag", "search_documents_by_keyword",
		"global_replace_keyword", "calculate", "get_server_time", "update_novel",
		"list_workspace_nodes", "create_workspace_node", "create_chapter_with_content",
		"write_document_content", "split_chapter_by_max_chars", "propose_document_update",
		"propose_selection_replace", "list_document_versions", "propose_version_restore",
		"restore_workspace_node", "update_workspace_node", "trash_workspace_node",
		"organize_workspace_tree", "cleanup_workspace_folders", "list_memory_items",
		"list_memory_review_items", "delete_memory_item", "propose_rewrite", "save_key_memory",
		"list_creative_assets", "create_character_asset", "create_world_rule", "update_creative_asset",
		"delete_creative_asset", "delete_creative_assets", "list_timeline_events",
		"create_timeline_event", "update_timeline_event", "reorder_timeline_events",
		"delete_timeline_event", "list_character_states", "update_character_state",
		"delete_character_state", "create_relationship_edge", "update_relationship_edge",
		"delete_relationship_edge", "list_character_attributes", "upsert_character_attribute",
		"delete_character_attribute", "list_inventory_items", "upsert_inventory_item",
		"delete_inventory_item", "list_map_locations", "upsert_map_location",
		"delete_map_location", "list_material_changes", "score_chapters_with_rubric",
	}
	got := coverage.ToolKeys()
	for _, name := range want {
		if !got[name] {
			t.Fatalf("missing tool coverage: %s", name)
		}
	}
}
