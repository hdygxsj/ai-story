package client_test

import (
	"context"
	"io"
	"net/http"
	"strings"
	"testing"

	"aistorycli/internal/client"
)

type roundTripFunc func(*http.Request) (*http.Response, error)

func (fn roundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return fn(req)
}

func response(status int, body string) *http.Response {
	return &http.Response{
		StatusCode: status,
		Body:       io.NopCloser(strings.NewReader(body)),
		Header:     make(http.Header),
	}
}

func TestClientAddsAuthorizationHeader(t *testing.T) {
	c := client.New("http://example.test", "token-123")
	c.HTTPClient = &http.Client{Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
		if got := r.Header.Get("Authorization"); got != "Bearer token-123" {
			t.Fatalf("missing auth header")
		}
		return response(http.StatusOK, `{"ok":true}`), nil
	})}

	body, err := c.Request(context.Background(), "GET", "/check", nil)
	if err != nil {
		t.Fatal(err)
	}
	if string(body) != `{"ok":true}` {
		t.Fatalf("body = %s", body)
	}
}

func TestClientSendsJSONBody(t *testing.T) {
	c := client.New("http://example.test", "")
	c.HTTPClient = &http.Client{Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
		if r.Header.Get("Content-Type") != "application/json" {
			t.Fatalf("content type = %q", r.Header.Get("Content-Type"))
		}
		body, _ := io.ReadAll(r.Body)
		if !strings.Contains(string(body), `"title":"Novel"`) {
			t.Fatalf("body = %s", body)
		}
		return response(http.StatusCreated, ""), nil
	})}

	if _, err := c.Request(context.Background(), "POST", "/novels", map[string]any{"title": "Novel"}); err != nil {
		t.Fatal(err)
	}
}

func TestClientReturnsHTTPErrorBody(t *testing.T) {
	c := client.New("http://example.test", "")
	c.HTTPClient = &http.Client{Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
		return response(http.StatusBadRequest, `{"detail":"bad"}`), nil
	})}

	_, err := c.Request(context.Background(), "GET", "/bad", nil)
	if err == nil {
		t.Fatal("expected error")
	}
	if !strings.Contains(err.Error(), "400") || !strings.Contains(err.Error(), "bad") {
		t.Fatalf("error = %v", err)
	}
}
