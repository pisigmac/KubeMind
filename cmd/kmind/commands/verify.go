package commands

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/kubemind/kmind/internal"
)

type VerifyResponse struct {
	Status       string `json:"status"`
	Verified     bool   `json:"verified"`
	HeadHash     string `json:"head_hash"`
	TotalEntries int    `json:"total_entries"`
}

func Verify(cfg *internal.Config, args []string) {
	workspace := cfg.Workspace.ID
	if workspace == "" {
		workspace = "default"
	}

	client := internal.NewAPIClient(cfg.TraceEndpoint, cfg.Workspace.APIKey, workspace)
	resp, err := client.Get(fmt.Sprintf("/v1/audit/verify?workspace_id=%s&limit=50", workspace))
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error verifying audit ledger: %v\n", err)
		os.Exit(1)
	}

	var data VerifyResponse
	if err := json.Unmarshal(resp, &data); err != nil {
		fmt.Fprintf(os.Stderr, "Error parsing verify response: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("=== KubeMind Cryptographic Audit Ledger Verification ===")
	fmt.Printf("Workspace:            %s\n", workspace)
	if data.Verified {
		fmt.Println("Integrity Status:     ✓ SHA-256 HASH CHAIN INTACT")
	} else {
		fmt.Println("Integrity Status:     ✗ TAMPERING DETECTED OR CHAIN BROKEN")
	}
	fmt.Printf("Head Chain Hash:      %s\n", data.HeadHash)
	fmt.Printf("Verified Entries:     %d\n", data.TotalEntries)
}
