package commands

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/pisigmac/tricore/internal"
)

type IngestRequest struct {
	Source string `json:"source"`
	Type   string `json:"type"`
}

type QueryRequest struct {
	Query   string            `json:"query"`
	Filters map[string]string `json:"filters,omitempty"`
}

func Knowledge(cfg *internal.Config, args []string) {
	if len(args) == 0 {
		fmt.Println("Usage: kmind knowledge <ingest|query|nodes> [args...]")
		return
	}

	client := internal.NewAPIClient(cfg.KnowledgeEndpoint, cfg.Workspace.APIKey, cfg.Workspace.ID)

	switch args[0] {
	case "ingest":
		if len(args) < 2 {
			fmt.Println("Usage: kmind knowledge ingest <path|url>")
			return
		}
		source := args[1]
		nodeType := "document"
		if strings.HasPrefix(source, "http") {
			nodeType = "web_page"
		} else if info, err := os.Stat(source); err == nil && info.IsDir() {
			nodeType = "directory"
		} else if filepath.Ext(source) == ".py" {
			nodeType = "code"
		}

		body := IngestRequest{Source: source, Type: nodeType}
		resp, err := client.Post("/v1/ingest", body)
		if err != nil {
			fmt.Printf("Error: %v\n", err)
			return
		}
		var data map[string]interface{}
		json.Unmarshal(resp, &data)
		fmt.Printf("Ingested %v nodes: %v\n", data["ingested"], data["node_ids"])

	case "query":
		if len(args) < 2 {
			fmt.Println("Usage: kmind knowledge query \"<query>\"")
			return
		}
		query := strings.Join(args[1:], " ")
		body := QueryRequest{Query: query}
		resp, err := client.Post("/v1/query", body)
		if err != nil {
			fmt.Printf("Error: %v\n", err)
			return
		}
		var data map[string]interface{}
		json.Unmarshal(resp, &data)
		fmt.Printf("Ingested %v nodes: %v\n", data["ingested"], data["node_ids"])

	case "nodes":
		if len(args) < 2 {
			fmt.Println("Usage: kmind knowledge nodes <node-id>")
			return
		}
		resp, err := client.Get("/v1/nodes/" + args[1])
		if err != nil {
			fmt.Printf("Error: %v\n", err)
			return
		}
		var data map[string]interface{}
		json.Unmarshal(resp, &data)
		fmt.Printf("Ingested %v nodes: %v\n", data["ingested"], data["node_ids"])

	default:
		fmt.Printf("Unknown knowledge command: %s\n", args[0])
	}
}
