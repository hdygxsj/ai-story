package config

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
)

const DefaultBaseURL = "http://localhost:8000"

type Config struct {
	BaseURL string `json:"base_url"`
	Token   string `json:"token"`
}

func (c Config) ResolveBaseURL(flagValue string) string {
	if flagValue != "" {
		return flagValue
	}
	if envValue := os.Getenv("AI_STORY_API_BASE"); envValue != "" {
		return envValue
	}
	if c.BaseURL != "" {
		return c.BaseURL
	}
	return DefaultBaseURL
}

func DefaultPath() (string, error) {
	dir, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, "ai-story", "config.json"), nil
}

func Load(path string) (Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return Config{}, nil
		}
		return Config{}, err
	}
	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

func Save(path string, cfg Config) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	return os.WriteFile(path, data, 0o600)
}
