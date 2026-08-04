package commands

import (
	"encoding/json"
	"fmt"

	"github.com/pisigmac/tricore/internal"
)

type healthResp struct {
	Status          string `json:"status"`
	Service         string `json:"service"`
	Version         string `json:"version"`
	Timestamp       string `json:"timestamp"`
	ProvidersLoaded int    `json:"providers_loaded"`
	CacheConnected  bool   `json:"cache_connected"`
}

func Status(cfg *internal.Config) {
	services := []struct {
		name string
		url  string
	}{
		{"router", cfg.GatewayEndpoint},
		{"mind", cfg.KnowledgeEndpoint},
		{"agents", cfg.APIEndpoint},
		{"sentinel", cfg.TraceEndpoint},
	}

	fmt.Println("=== KubeMind Status ===")
	for _, svc := range services {
		client := internal.NewAPIClient(svc.url, cfg.Workspace.APIKey, cfg.Workspace.ID)
		data, err := client.Get("/health")
		if err != nil {
			fmt.Printf("  %-12s  down  %v\n", svc.name, err)
			continue
		}
		var h healthResp
		_ = json.Unmarshal(data, &h)
		label := h.Status
		if label == "" {
			label = "ok"
		}
		fmt.Printf("  %-12s  %s  (v%s)\n", svc.name, label, h.Version)
	}
	fmt.Printf("\nDashboard: %s\n", cfg.DashboardURL)
}
