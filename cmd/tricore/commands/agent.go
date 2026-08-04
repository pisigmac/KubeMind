package commands

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/pisigmac/tricore/internal"
)

type MissionRequest struct {
	Prompt string `json:"prompt"`
	Mode   string `json:"mode"`
}

type MissionResponse struct {
	ID      string `json:"id"`
	Status  string `json:"status"`
	Result  string `json:"result,omitempty"`
	Error   string `json:"error,omitempty"`
}

func Agent(cfg *internal.Config, args []string) {
	if len(args) == 0 {
		fmt.Println("Usage: kmind agent <run|repl|list|logs> [args...]")
		return
	}

	client := internal.NewAPIClient(cfg.APIEndpoint, cfg.Workspace.APIKey, cfg.Workspace.ID)

	switch args[0] {
	case "run":
		if len(args) < 2 {
			fmt.Println("Usage: kmind agent run \"<prompt>\"")
			return
		}
		prompt := strings.Join(args[1:], " ")
		body := MissionRequest{Prompt: prompt, Mode: "sync"}
		respData, err := client.Post("/v1/missions", body)
		if err != nil {
			fmt.Printf("Error: %v\n", err)
			return
		}
		var resp MissionResponse
		json.Unmarshal(respData, &resp)
		fmt.Printf("Mission %s: %s\n", resp.ID, resp.Status)
		if resp.Result != "" {
			fmt.Println("\n--- Result ---")
			fmt.Println(resp.Result)
		}
		if resp.Error != "" {
			fmt.Println("\n--- Error ---")
			fmt.Println(resp.Error)
		}

	case "repl":
		fmt.Println("KubeMind agent REPL. Type 'exit' to quit.")
		scanner := bufio.NewScanner(os.Stdin)
		for {
			fmt.Print("> ")
			if !scanner.Scan() {
				break
			}
			line := scanner.Text()
			if line == "exit" {
				break
			}
			body := MissionRequest{Prompt: line, Mode: "sync"}
			respData, err := client.Post("/v1/missions", body)
			if err != nil {
				fmt.Printf("Error: %v\n", err)
				continue
			}
			var resp MissionResponse
			json.Unmarshal(respData, &resp)
			fmt.Println(resp.Result)
		}

	case "list":
		respData, err := client.Get("/v1/missions")
		if err != nil {
			fmt.Printf("Error: %v\n", err)
			return
		}
		fmt.Println(string(respData))

	default:
		fmt.Printf("Unknown agent command: %s\n", args[0])
	}
}
