package command_test

import (
	"bytes"
	"context"
	"io"
	"net/http"
	"strings"
	"testing"

	"aistorycli/internal/command"
	"aistorycli/internal/config"
)

type roundTripFunc func(*http.Request) (*http.Response, error)

func (fn roundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return fn(req)
}

func testResponse(status int, body string) *http.Response {
	return &http.Response{
		StatusCode: status,
		Body:       io.NopCloser(strings.NewReader(body)),
		Header:     make(http.Header),
	}
}

func TestAPIRequestSendsMethodAndPath(t *testing.T) {
	var stdout bytes.Buffer
	env := &command.Env{
		Stdout: &stdout,
		Stderr: io.Discard,
		Config: config.Config{BaseURL: "http://example.test", Token: "token-123"},
		HTTPClient: &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			if req.Method != http.MethodGet {
				t.Fatalf("method = %s", req.Method)
			}
			if req.URL.Path != "/health" {
				t.Fatalf("path = %s", req.URL.Path)
			}
			if req.Header.Get("Authorization") != "Bearer token-123" {
				t.Fatalf("missing auth header")
			}
			return testResponse(http.StatusOK, `{"status":"ok"}`), nil
		})},
	}

	code := command.Execute(context.Background(), env, []string{"api", "request", "GET", "/health"})
	if code != 0 {
		t.Fatalf("exit code = %d", code)
	}
	if !strings.Contains(stdout.String(), `"status":"ok"`) {
		t.Fatalf("stdout = %s", stdout.String())
	}
}

func TestAPIRoutesPrintsCoverage(t *testing.T) {
	var stdout bytes.Buffer
	env := &command.Env{Stdout: &stdout, Stderr: io.Discard}

	code := command.Execute(context.Background(), env, []string{"api", "routes"})
	if code != 0 {
		t.Fatalf("exit code = %d", code)
	}
	if !strings.Contains(stdout.String(), "POST /novels/{novel_id}/agent/tools/{tool_name}") {
		t.Fatalf("routes output = %s", stdout.String())
	}
	if !strings.Contains(stdout.String(), "GET /local-scoring-skill/SKILL.md") {
		t.Fatalf("routes output missing scoring skill route = %s", stdout.String())
	}
	if !strings.Contains(stdout.String(), "GET /local-agent-skills") {
		t.Fatalf("routes output missing local agent skills manifest route = %s", stdout.String())
	}
	if !strings.Contains(stdout.String(), "GET /local-novel-skills/{skill_name}/SKILL.md") {
		t.Fatalf("routes output missing novel skills route = %s", stdout.String())
	}
	if !strings.Contains(stdout.String(), "GET /local-novel-skills") {
		t.Fatalf("routes output missing novel skills list route = %s", stdout.String())
	}
}
