package commands

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/kubemind/kmind/internal"
)

type AnalyticsResponse struct {
	WorkspaceID       string                 `json:"workspace_id"`
	WindowHours       int                    `json:"window_hours"`
	TotalRequests     int                    `json:"total_requests"`
	PromptTokens      int                    `json:"prompt_tokens"`
	CompletionTokens  int                    `json:"completion_tokens"`
	TotalTokens       int                    `json:"total_tokens"`
	EstimatedSpendUSD float64                `json:"estimated_spend_usd"`
	Providers         map[string]ProviderRow `json:"providers"`
	Models            map[string]ProviderRow `json:"models"`
}

type ProviderRow struct {
	Requests int     `json:"requests"`
	Tokens   int     `json:"tokens"`
	SpendUSD float64 `json:"spend_usd"`
}

func Analytics(cfg *internal.Config, args []string) {
	window := "24"
	if len(args) > 0 {
		window = args[0]
	}

	client := internal.NewAPIClient(cfg.GatewayEndpoint, cfg.Workspace.APIKey, cfg.Workspace.ID)
	resp, err := client.Get(fmt.Sprintf("/v1/usage/analytics?window_hours=%s", window))
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error fetching analytics: %v\n", err)
		os.Exit(1)
	}

	var data AnalyticsResponse
	if err := json.Unmarshal(resp, &data); err != nil {
		fmt.Fprintf(os.Stderr, "Error parsing analytics: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("=== KubeMind Financial & Usage Analytics ===")
	fmt.Printf("Workspace:            %s\n", data.WorkspaceID)
	fmt.Printf("Time Window:          Last %d Hours\n", data.WindowHours)
	fmt.Printf("Total Requests:       %d\n", data.TotalRequests)
	fmt.Printf("Prompt Tokens:        %d\n", data.PromptTokens)
	fmt.Printf("Completion Tokens:    %d\n", data.CompletionTokens)
	fmt.Printf("Total Tokens:         %d\n", data.TotalTokens)
	fmt.Printf("Estimated Spend:      $%.4f USD\n\n", data.EstimatedSpendUSD)

	if len(data.Providers) > 0 {
		fmt.Println("--- Provider Spend Distribution ---")
		for p, row := range data.Providers {
			fmt.Printf("  • %-15s %5d reqs | %8d tokens | $%.4f USD\n", p, row.Requests, row.Tokens, row.SpendUSD)
		}
	}
}
