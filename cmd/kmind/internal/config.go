package internal

import (
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

	// If no config file is found on disk, gracefully return DefaultConfig (which resolves from env)
	return DefaultConfig(), nil
}

func getEnv(keys []string, fallback string) string {
	for _, k := range keys {
		if v := os.Getenv(k); v != "" {
			return v
		}
	}
	return fallback
}

func DefaultConfig() *Config {
	return &Config{
		APIEndpoint:       getEnv([]string{"AGENTS_URL", "KUBEMIND_AGENTS_URL"}, "http://localhost:9082"),
		KnowledgeEndpoint: getEnv([]string{"MIND_URL", "KUBEMIND_MIND_URL"}, "http://localhost:9081"),
		GatewayEndpoint:   getEnv([]string{"ROUTER_URL", "KUBEMIND_ROUTER_URL"}, "http://localhost:9080"),
		TraceEndpoint:     getEnv([]string{"SENTINEL_URL", "TRACER_URL", "KUBEMIND_SENTINEL_URL"}, "http://localhost:9083"),
		DashboardURL:      getEnv([]string{"DASHBOARD_URL", "KUBEMIND_DASHBOARD_URL"}, "http://localhost:9000"),
		Workspace: struct {
			ID     string `yaml:"id"`
			APIKey string `yaml:"api_key"`
		}{
			ID:     getEnv([]string{"KUBEMIND_WORKSPACE", "WORKSPACE_ID"}, "default"),
			APIKey: getEnv([]string{"KUBEMIND_API_KEY", "API_KEY"}, "kmind-local-dev-key"),
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
