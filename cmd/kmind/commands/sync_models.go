package commands

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"sort"
	"strings"
	"time"

	"github.com/kubemind/kmind/internal"
)

type SyncResponse struct {
	Status  string      `json:"status"`
	Summary SyncSummary `json:"summary"`
}

type SyncSummary struct {
	TotalModels int                     `json:"total_models"`
	Providers   map[string]ProviderSync `json:"providers"`
}

type ProviderSync struct {
	Healthy    bool     `json:"healthy"`
	Priority   int      `json:"priority"`
	Free       bool     `json:"free"`
	Models     []string `json:"models"`
	Discovered int      `json:"discovered"`
	Error      string   `json:"error,omitempty"`
}

func SyncModels(cfg *internal.Config, args []string) {
	gateway := cfg.GatewayEndpoint
	if gateway == "" {
		gateway = cfg.APIEndpoint
	}
	if gateway == "" {
		gateway = "http://localhost:9080"
	}

	wsID := cfg.Workspace.ID
	if wsID == "" {
		wsID = "default"
	}
	apiKey := cfg.Workspace.APIKey
	if apiKey == "" {
		apiKey = "kmind-local-dev-key"
	}

	fmt.Printf("\n\033[1;34m====================================================================\033[0m\n")
	fmt.Printf("\033[1;34m       🔄 KubeMind Upstream Dynamic Model Catalog Sync             \033[0m\n")
	fmt.Printf("\033[1;34m====================================================================\033[0m\n")
	fmt.Printf("  Gateway Endpoint:  \033[36m%s\033[0m\n", gateway)
	fmt.Printf("  Active Workspace:  \033[36m%s\033[0m\n\n", wsID)

	fmt.Printf("  \033[2mScanning live /models APIs across OpenAI, Gemini, Groq, Ollama...\033[0m\n\n")

	url := fmt.Sprintf("%s/v1/models/sync", strings.TrimRight(gateway, "/"))
	req, err := http.NewRequest("POST", url, bytes.NewBuffer([]byte("{}")))
	if err != nil {
		fmt.Fprintf(os.Stderr, "  \033[31m❌ Failed to create sync request: %v\033[0m\n\n", err)
		return
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Workspace-ID", wsID)
	req.Header.Set("X-API-Key", apiKey)

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		fmt.Fprintf(os.Stderr, "  \033[31m❌ Gateway connection failed: %v\033[0m\n\n", err)
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		fmt.Fprintf(os.Stderr, "  \033[31m❌ Sync request returned HTTP %d: %s\033[0m\n\n", resp.StatusCode, string(body))
		return
	}

	var syncResp SyncResponse
	if err := json.Unmarshal(body, &syncResp); err != nil {
		fmt.Fprintf(os.Stderr, "  \033[31m❌ Failed to parse response: %v\033[0m\n\n", err)
		return
	}

	// Print Provider Table
	fmt.Printf("  %-16s %-10s %-8s %-12s %-32s\n", "PROVIDER", "STATUS", "COST", "DISCOVERED", "SAMPLE MODELS")
	fmt.Printf("  %s\n", strings.Repeat("─", 80))

	// Sort provider names
	var provNames []string
	for p := range syncResp.Summary.Providers {
		provNames = append(provNames, p)
	}
	sort.Strings(provNames)

	for _, name := range provNames {
		info := syncResp.Summary.Providers[name]
		statusStr := "\033[32mONLINE\033[0m"
		if !info.Healthy {
			statusStr = "\033[31mOFFLINE\033[0m"
		}
		costStr := "\033[32mFREE\033[0m"
		if !info.Free {
			costStr = "\033[33mPAID\033[0m"
		}

		discStr := fmt.Sprintf("%d models", len(info.Models))
		if info.Discovered > 0 {
			discStr = fmt.Sprintf("\033[1;32m+%d live\033[0m (%d)", info.Discovered, len(info.Models))
		}

		samples := ""
		if len(info.Models) > 0 {
			limit := 3
			if len(info.Models) < limit {
				limit = len(info.Models)
			}
			samples = strings.Join(info.Models[:limit], ", ")
			if len(info.Models) > limit {
				samples += "..."
			}
		}

		fmt.Printf("  %-16s %-19s %-17s %-20s %-32s\n", name, statusStr, costStr, discStr, samples)
	}

	fmt.Printf("  %s\n", strings.Repeat("─", 80))
	fmt.Printf("  \033[1;32m✓ Total Models Registered:\033[0m \033[1m%d\033[0m across all active providers.\n", syncResp.Summary.TotalModels)
	fmt.Printf("  💡 Run \033[36mkmind chat\033[0m or switch models with \033[36m/model <name>\033[0m.\n\n")
}
