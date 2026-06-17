package config_test

import (
	"testing"

	"aistorycli/internal/config"
)

func TestConfigBaseURLPriority(t *testing.T) {
	t.Setenv("AI_STORY_API_BASE", "http://env.example")
	cfg := config.Config{BaseURL: "http://saved.example"}

	if got := cfg.ResolveBaseURL("http://flag.example"); got != "http://flag.example" {
		t.Fatalf("flag base URL = %q", got)
	}
	if got := cfg.ResolveBaseURL(""); got != "http://env.example" {
		t.Fatalf("env base URL = %q", got)
	}

	t.Setenv("AI_STORY_API_BASE", "")
	if got := cfg.ResolveBaseURL(""); got != "http://saved.example" {
		t.Fatalf("saved base URL = %q", got)
	}

	cfg.BaseURL = ""
	if got := cfg.ResolveBaseURL(""); got != config.DefaultBaseURL {
		t.Fatalf("default base URL = %q", got)
	}
}

func TestConfigSaveLoadRoundTrip(t *testing.T) {
	path := t.TempDir() + "/config.json"
	cfg := config.Config{BaseURL: "http://local.test", Token: "token-123"}
	if err := config.Save(path, cfg); err != nil {
		t.Fatal(err)
	}

	got, err := config.Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if got != cfg {
		t.Fatalf("loaded config = %#v, want %#v", got, cfg)
	}
}
