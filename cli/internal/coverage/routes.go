package coverage

import "fmt"

type Route struct {
	Method string `json:"method"`
	Path   string `json:"path"`
	Group  string `json:"group"`
}

var Routes = []Route{
	{"POST", "/auth/register", "auth"},
	{"POST", "/auth/login", "auth"},
	{"GET", "/auth/me", "auth"},
	{"POST", "/model-profiles", "model-profiles"},
	{"GET", "/model-profiles", "model-profiles"},
	{"PATCH", "/model-profiles/{profile_id}", "model-profiles"},
	{"DELETE", "/model-profiles/{profile_id}", "model-profiles"},
	{"POST", "/model-profiles/test-connectivity", "model-profiles"},
	{"POST", "/novels", "novels"},
	{"POST", "/novels/import", "novels"},
	{"GET", "/novels", "novels"},
	{"PATCH", "/novels/{novel_id}", "novels"},
	{"GET", "/novels/{novel_id}/export", "novels"},
	{"GET", "/novels/{novel_id}/nodes/{node_id}/export", "workspace"},
	{"POST", "/novels/{novel_id}/nodes", "workspace"},
	{"GET", "/novels/{novel_id}/nodes", "workspace"},
	{"DELETE", "/novels/{novel_id}/nodes/trash", "workspace"},
	{"PATCH", "/novels/{novel_id}/nodes/reorder", "workspace"},
	{"PATCH", "/novels/{novel_id}/nodes/{node_id}", "workspace"},
	{"GET", "/documents/{document_id}", "documents"},
	{"PATCH", "/documents/{document_id}", "documents"},
	{"GET", "/documents/{document_id}/versions", "documents"},
	{"POST", "/documents/{document_id}/versions/{version_id}/restore", "documents"},
	{"GET", "/novels/{novel_id}/confirmations", "confirmations"},
	{"GET", "/novels/{novel_id}/confirmations/history", "confirmations"},
	{"POST", "/confirmations/{confirmation_id}/approve", "confirmations"},
	{"POST", "/confirmations/{confirmation_id}/reject", "confirmations"},
	{"GET", "/novels/{novel_id}/conversations", "conversations"},
	{"POST", "/novels/{novel_id}/conversations", "conversations"},
	{"GET", "/novels/{novel_id}/conversations/{conversation_id}", "conversations"},
	{"PATCH", "/novels/{novel_id}/conversations/{conversation_id}", "conversations"},
	{"DELETE", "/novels/{novel_id}/conversations/{conversation_id}", "conversations"},
	{"GET", "/novels/{novel_id}/conversations/{conversation_id}/messages", "conversations"},
	{"GET", "/novels/{novel_id}/context-settings", "context-settings"},
	{"PATCH", "/novels/{novel_id}/context-settings", "context-settings"},
	{"POST", "/novels/{novel_id}/memory-review-items", "memory"},
	{"GET", "/novels/{novel_id}/memory-review-items", "memory"},
	{"POST", "/memory-review-items/{item_id}/approve", "memory"},
	{"POST", "/memory-review-items/{item_id}/reject", "memory"},
	{"GET", "/novels/{novel_id}/memory-items", "memory"},
	{"POST", "/novels/{novel_id}/memory-items", "memory"},
	{"DELETE", "/memory-items/{item_id}", "memory"},
	{"POST", "/novels/{novel_id}/creative-assets", "materials"},
	{"GET", "/novels/{novel_id}/creative-assets", "materials"},
	{"PATCH", "/novels/{novel_id}/creative-assets/{asset_id}", "materials"},
	{"DELETE", "/novels/{novel_id}/creative-assets/{asset_id}", "materials"},
	{"POST", "/novels/{novel_id}/timeline-events", "materials"},
	{"GET", "/novels/{novel_id}/timeline-events", "materials"},
	{"PATCH", "/novels/{novel_id}/timeline-events/{event_id}", "materials"},
	{"POST", "/novels/{novel_id}/timeline-events/reorder", "materials"},
	{"DELETE", "/novels/{novel_id}/timeline-events/{event_id}", "materials"},
	{"POST", "/novels/{novel_id}/character-states", "materials"},
	{"GET", "/novels/{novel_id}/character-states", "materials"},
	{"PATCH", "/novels/{novel_id}/character-states/{state_id}", "materials"},
	{"DELETE", "/novels/{novel_id}/character-states/{state_id}", "materials"},
	{"POST", "/novels/{novel_id}/relationship-edges", "materials"},
	{"GET", "/novels/{novel_id}/relationship-edges", "materials"},
	{"PATCH", "/novels/{novel_id}/relationship-edges/{edge_id}", "materials"},
	{"DELETE", "/novels/{novel_id}/relationship-edges/{edge_id}", "materials"},
	{"GET", "/novels/{novel_id}/material-changes", "materials"},
	{"GET", "/novels/{novel_id}/rag/search", "rag"},
	{"GET", "/novels/{novel_id}/search", "search"},
	{"POST", "/novels/{novel_id}/agent/messages", "agent"},
	{"POST", "/novels/{novel_id}/agent/messages/stream", "agent"},
	{"GET", "/agent-tools", "tools"},
	{"GET", "/agent-tools/{tool_name}", "tools"},
	{"POST", "/novels/{novel_id}/agent/tools/{tool_name}", "tools"},
}

func RouteKeys() map[string]bool {
	keys := make(map[string]bool, len(Routes))
	for _, route := range Routes {
		keys[fmt.Sprintf("%s %s", route.Method, route.Path)] = true
	}
	return keys
}
