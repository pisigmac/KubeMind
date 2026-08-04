package commands

import (
	"encoding/json"
	"fmt"

	"github.com/pisigmac/tricore/internal"
)

func Gateway(cfg *internal.Config, args []string) {
	if len(args) == 0 {
		fmt.Println("Usage: kmind gateway <usage|providers|cache-clear>")
		return
	}

	client := internal.NewAPIClient(cfg.GatewayEndpoint, cfg.Workspace.APIKey, cfg.Workspace.ID)

	switch args[0] {
	case "usage":
		resp, err := client.Get("/v1/usage")
		if err != nil {
			fmt.Printf("Error: %v\n", err)
			return
		}
		var data map[string]interface{}
		json.Unmarshal(resp, &data)
		fmt.Printf("Workspace: %s\n", data["workspace_id"])
		fmt.Printf("Total requests: %.0f\n", data["total_requests"])
		fmt.Printf("Total tokens: %.0f\n", data["total_tokens"])
		fmt.Printf("Estimated cost: $%.4f\n", data["estimated_cost"])

	case "providers":
		resp, err := client.Get("/v1/providers/health")
		if err != nil {
			fmt.Printf("Error: %v\n", err)
			return
		}
		var data []map[string]interface{}
		json.Unmarshal(resp, &data)
		fmt.Println("Providers:")
		for _, p := range data {
			status := "❌"
			if p["healthy"].(bool) {
				status = "✅"
			}
			fmt.Printf("  %s %s (priority=%v, free=%v, circuit=%s, failures=%v)\n",
				status, p["name"], p["priority"], p["free"], p["circuit_state"], p["failure_count"])
		}

	case "cache-clear":
		resp, err := client.Post("/v1/cache/clear", map[string]string{})
		if err != nil {
			fmt.Printf("Error: %v\n", err)
			return
		}
		var data []map[string]interface{}
		json.Unmarshal(resp, &data)
		fmt.Println("Providers:")
		for _, p := range data {
			status := "❌"
			if p["healthy"].(bool) {
				status = "✅"
			}
			fmt.Printf("  %s %s (priority=%v, free=%v, circuit=%s, failures=%v)\n",
				status, p["name"], p["priority"], p["free"], p["circuit_state"], p["failure_count"])
		}

	default:
		fmt.Printf("Unknown gateway command: %s\n", args[0])
	}
}
