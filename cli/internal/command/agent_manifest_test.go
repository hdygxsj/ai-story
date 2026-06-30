package command_test

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"testing"

	"aistorycli/internal/command"
)

func TestAgentManifestExposesWritingBusinessCapabilities(t *testing.T) {
	var stdout bytes.Buffer
	env := &command.Env{Stdout: &stdout, Stderr: io.Discard}

	code := command.Execute(context.Background(), env, []string{"agent", "manifest"})
	if code != 0 {
		t.Fatalf("exit code = %d", code)
	}

	var manifest struct {
		Routes []struct {
			Method string `json:"method"`
			Path   string `json:"path"`
			Group  string `json:"group"`
		} `json:"routes"`
		Tools []string `json:"tools"`
	}
	if err := json.Unmarshal(stdout.Bytes(), &manifest); err != nil {
		t.Fatalf("manifest is not JSON: %v\n%s", err, stdout.String())
	}
	if !bytes.Contains(stdout.Bytes(), []byte(`"method"`)) || bytes.Contains(stdout.Bytes(), []byte(`"Method"`)) {
		t.Fatalf("manifest route fields should be lowercase JSON keys:\n%s", stdout.String())
	}

	routeKeys := map[string]bool{}
	for _, route := range manifest.Routes {
		routeKeys[route.Method+" "+route.Path] = true
	}
	for _, want := range []string{
		"GET /novels/{novel_id}/creative-assets",
		"GET /novels/{novel_id}/timeline-events",
		"GET /novels/{novel_id}/character-attributes",
		"GET /novels/{novel_id}/inventory-items",
		"GET /novels/{novel_id}/map-locations",
		"GET /novels/{novel_id}/memory-items",
		"POST /novels/{novel_id}/agent/tools/{tool_name}",
		"GET /local-agent-skills",
		"GET /local-scoring-skill/SKILL.md",
		"GET /local-novel-skills",
		"GET /local-novel-skills/{skill_name}/SKILL.md",
	} {
		if !routeKeys[want] {
			t.Fatalf("manifest missing route %s", want)
		}
	}

	toolKeys := map[string]bool{}
	for _, tool := range manifest.Tools {
		toolKeys[tool] = true
	}
	for _, want := range []string{
		"create_chapter_with_content",
		"list_creative_assets",
		"list_timeline_events",
		"upsert_character_attribute",
		"upsert_inventory_item",
		"upsert_map_location",
		"save_key_memory",
		"search_documents_by_keyword",
		"score_chapters_with_rubric",
	} {
		if !toolKeys[want] {
			t.Fatalf("manifest missing tool %s", want)
		}
	}
}
