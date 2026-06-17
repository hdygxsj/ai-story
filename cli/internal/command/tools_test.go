package command_test

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"testing"

	"aistorycli/internal/command"
	"aistorycli/internal/config"
)

func TestToolsRunPostsArguments(t *testing.T) {
	var stdout bytes.Buffer
	env := &command.Env{
		Stdout: &stdout,
		Stderr: io.Discard,
		Config: config.Config{BaseURL: "http://example.test"},
		HTTPClient: &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			if req.Method != http.MethodPost {
				t.Fatalf("method = %s", req.Method)
			}
			if req.URL.Path != "/novels/novel-1/agent/tools/calculate" {
				t.Fatalf("path = %s", req.URL.Path)
			}
			var body map[string]any
			if err := json.NewDecoder(req.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			args := body["arguments"].(map[string]any)
			if args["expression"] != "1+2" {
				t.Fatalf("arguments = %#v", args)
			}
			return testResponse(http.StatusOK, `{"result":{"result":"3"}}`), nil
		})},
	}

	code := command.Execute(context.Background(), env, []string{"tools", "run", "novel-1", "calculate", "--arg", "expression=1+2"})
	if code != 0 {
		t.Fatalf("exit code = %d", code)
	}
	if !strings.Contains(stdout.String(), `"result":"3"`) {
		t.Fatalf("stdout = %s", stdout.String())
	}
}

func TestToolsRunParsesJSONArgsAndDocumentID(t *testing.T) {
	env := &command.Env{
		Stdout: io.Discard,
		Stderr: io.Discard,
		Config: config.Config{BaseURL: "http://example.test"},
		HTTPClient: &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			var body map[string]any
			if err := json.NewDecoder(req.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			if body["document_id"] != "doc-1" {
				t.Fatalf("document_id = %#v", body["document_id"])
			}
			args := body["arguments"].(map[string]any)
			ids := args["asset_ids"].([]any)
			if len(ids) != 2 || ids[0] != "a" || ids[1] != "b" {
				t.Fatalf("asset_ids = %#v", ids)
			}
			return testResponse(http.StatusOK, `{"result":{"status":"ok"}}`), nil
		})},
	}

	code := command.Execute(
		context.Background(),
		env,
		[]string{"tools", "run", "novel-1", "delete_creative_assets", "--json-arg", `asset_ids=["a","b"]`, "--document-id", "doc-1", "--yes"},
	)
	if code != 0 {
		t.Fatalf("exit code = %d", code)
	}
}

func TestToolsListAndSchemaCallBackend(t *testing.T) {
	var paths []string
	env := &command.Env{
		Stdout: io.Discard,
		Stderr: io.Discard,
		Config: config.Config{BaseURL: "http://example.test"},
		HTTPClient: &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			paths = append(paths, req.URL.Path)
			return testResponse(http.StatusOK, `[]`), nil
		})},
	}

	if code := command.Execute(context.Background(), env, []string{"tools", "list"}); code != 0 {
		t.Fatalf("list exit code = %d", code)
	}
	if code := command.Execute(context.Background(), env, []string{"tools", "schema", "calculate"}); code != 0 {
		t.Fatalf("schema exit code = %d", code)
	}
	if strings.Join(paths, ",") != "/agent-tools,/agent-tools/calculate" {
		t.Fatalf("paths = %#v", paths)
	}
}
