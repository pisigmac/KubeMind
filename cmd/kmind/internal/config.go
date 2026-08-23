package internal

import (
	"fmt"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

type Config struct {
	APIEndpoint       string `yaml:"api_endpoint"`
	KnowledgeEndpoint string `yaml:"knowledge_endpoint"`
	GatewayEndpoint   string `yaml:"gateway_endpoint"`
	TraceEndpoint     string `yaml:"trace_endpoint"`
	DashboardURL      string `yaml:"dashboard_url"`
	Workspace         struct {
		ID     string `yaml:"id"`
		APIKey string `yaml:"api_key"`
	} `yaml:"workspace"`
}

func configCandidates(home string) []string {
	return []string{
		filepath.Join(home, ".kmind", "config.yaml"),
		filepath.Join(home, ".tricore", "config.yaml"), // transitional fallback
	}
}

func LoadConfig() (*Config, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return nil, err
	}

	for _, configPath := range configCandidates(home) {
		data, err := os.ReadFile(configPath)
		if err != nil {
			continue
		}
		var cfg Config
		if err := yaml.Unmarshal(data, &cfg); err != nil {
			return nil, err
		}
		return &cfg, nil
	}

	return nil, fmt.Errorf("config not found — run `kmind init` first (looked for ~/.kmind/config.yaml)")
}

func DefaultConfig() *Config {
	return &Config{
		APIEndpoint:       "http://localhost:9082",
		KnowledgeEndpoint: "http://localhost:9081",
		GatewayEndpoint:   "http://localhost:9080",
		TraceEndpoint:     "http://localhost:9083",
		DashboardURL:      "http://localhost:9000",
		Workspace: struct {
			ID     string `yaml:"id"`
			APIKey string `yaml:"api_key"`
		}{
			ID:     "default",
			APIKey: "kmind-local-dev-key",
		},
	}
}

func (c *Config) Save() error {
	home, err := os.UserHomeDir()
	if err != nil {
		return err
	}
	dir := filepath.Join(home, ".kmind")
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	data, err := yaml.Marshal(c)
	if err != nil {
		return err
	}

	return os.WriteFile(filepath.Join(dir, "config.yaml"), data, 0600)
}
