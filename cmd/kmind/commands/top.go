package commands

import (
	"encoding/json"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/kubemind/kmind/internal"
)

type ProviderHealth struct {
	Name         string  `json:"name"`
	Healthy      bool    `json:"healthy"`
	CircuitState string  `json:"circuit_state"`
	LatencyEWMA  float64 `json:"latency_ewma"`
	Priority     int     `json:"priority"`
	Free         bool    `json:"free"`
}

type CacheStats struct {
	Connected       bool    `json:"connected"`
	Entries         int     `json:"entries"`
	SemanticEnabled bool    `json:"semantic_enabled"`
	SemanticThresh  float64 `json:"semantic_threshold"`
}

func Top(cfg *internal.Config, args []string) {
	// Setup clean exit on SIGINT
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	// Initial render
	renderTop(cfg)

	for {
		select {
		case <-sigChan:
			fmt.Print("\033[?25h") // Show cursor
			fmt.Println("\nMonitor stopped.")
			return
		case <-ticker.C:
			renderTop(cfg)
		}
	}
}

func renderTop(cfg *internal.Config) {
	client := internal.NewAPIClient(cfg.GatewayEndpoint, cfg.Workspace.APIKey, cfg.Workspace.ID)
	sentinelClient := internal.NewAPIClient(cfg.TraceEndpoint, cfg.Workspace.APIKey, cfg.Workspace.ID)

	// 1. Fetch Provider Health
	var providers []ProviderHealth
	if resp, err := client.Get("/v1/providers/health"); err == nil {
		json.Unmarshal(resp, &providers)
	}

	// 2. Fetch Usage Analytics (Last 1h)
	var analytics AnalyticsResponse
	if resp, err := client.Get("/v1/usage/analytics?window_hours=1"); err == nil {
		json.Unmarshal(resp, &analytics)
	}

	// 3. Fetch Cache Stats
	var cacheStats CacheStats
	if resp, err := client.Get("/v1/cache/stats"); err == nil {
		json.Unmarshal(resp, &cacheStats)
	}

	// 4. Fetch Sentinel Stats
	type SentinelStats struct {
		TotalSpans int `json:"total_spans"`
		Workspaces int `json:"workspaces"`
		Services   int `json:"services"`
	}
	var sStats SentinelStats
	if resp, err := sentinelClient.Get("/v1/stats"); err == nil {
		json.Unmarshal(resp, &sStats)
	}

	// Render Terminal HUD (clear screen)
	fmt.Print("\033[H\033[2J\033[?25l") // Clear screen and hide cursor

	fmt.Println("=========================================================================================")
	fmt.Printf(" 🧠 \033[1;36mKubeMind Enterprise Cluster HUD\033[0m — %s (Workspace: \033[1m%s\033[0m)\n",
		time.Now().Format("2006-01-02 15:04:05 MST"), cfg.Workspace.ID)
	fmt.Println("=========================================================================================")

	// Section 1: Cluster Health Summary
	fmt.Println("\n\033[1;33m[1. System Activity & Financials (Last 60 mins)]\033[0m")
	fmt.Printf("  • Requests: \033[1m%-6d\033[0m | Tokens: \033[1m%-8d\033[0m | Spend: \033[1;32m$%.4f USD\033[0m\n",
		analytics.TotalRequests, analytics.TotalTokens, analytics.EstimatedSpendUSD)
	fmt.Printf("  • Spans Tracked: \033[1m%-6d\033[0m | Active Workspaces: \033[1m%-3d\033[0m | Connected Services: \033[1m%d\033[0m\n",
		sStats.TotalSpans, sStats.Workspaces, sStats.Services)
	fmt.Printf("  • Semantic Cache: \033[1m%s\033[0m (Threshold: %.2f) | Exact Cache Entries: \033[1m%d\033[0m\n",
		formatBool(cacheStats.SemanticEnabled), cacheStats.SemanticThresh, cacheStats.Entries)

	// Section 2: Upstream LLM Providers & Circuit Breaker
	fmt.Println("\n\033[1;33m[2. Upstream LLM Providers & Circuit Breakers]\033[0m")
	fmt.Printf("  %-16s %-10s %-14s %-12s %-10s\n", "PROVIDER", "HEALTH", "CIRCUIT", "LATENCY EWMA", "TIER")
	fmt.Println("  ---------------------------------------------------------------------------------")
	if len(providers) == 0 {
		fmt.Println("  (No provider backends configured or gateway offline)")
	} else {
		for _, p := range providers {
			healthStr := "\033[32mONLINE\033[0m"
			if !p.Healthy {
				healthStr = "\033[31mOFFLINE\033[0m"
			}

			circuitStr := "\033[32mCLOSED\033[0m"
			if p.CircuitState == "OPEN" {
				circuitStr = "\033[31mOPEN\033[0m"
			} else if p.CircuitState == "HALF_OPEN" {
				circuitStr = "\033[33mHALF_OPEN\033[0m"
			}

			tierStr := "Cloud Paid"
			if p.Free {
				tierStr = "\033[36mFree/Local\033[0m"
			}

			latencyStr := fmt.Sprintf("%.1fms", p.LatencyEWMA)
			if p.LatencyEWMA <= 0 {
				latencyStr = "—"
			}

			fmt.Printf("  %-16s %-19s %-23s %-12s %-10s\n",
				p.Name, healthStr, circuitStr, latencyStr, tierStr)
		}
	}

	fmt.Println("\n=========================================================================================")
	fmt.Println(" Press \033[1mCtrl+C\033[0m to exit monitor.")
}

func formatBool(b bool) string {
	if b {
		return "ACTIVE (HNSW)"
	}
	return "DISABLED"
}
