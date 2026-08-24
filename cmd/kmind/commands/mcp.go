package commands

import (
	"fmt"
	"os"
	"os/exec"

	"github.com/kubemind/kmind/internal"
)

func MCP(cfg *internal.Config, args []string) {
	fmt.Println("🚀 Starting KubeMind Model Context Protocol (MCP) Server (JSON-RPC stdio)...")

	cmd := exec.Command("python3", "-m", "router.mcp_server")
	cmd.Dir = "services/router"
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	// Forward workspace credentials
	cmd.Env = append(os.Environ(),
		fmt.Sprintf("ROUTER_URL=%s", cfg.GatewayEndpoint),
		fmt.Sprintf("SENTINEL_URL=%s", cfg.TraceEndpoint),
		fmt.Sprintf("KUBEMIND_API_KEY=%s", cfg.Workspace.APIKey),
		fmt.Sprintf("KUBEMIND_WORKSPACE=%s", cfg.Workspace.ID),
	)

	if err := cmd.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "MCP server exited with error: %v\n", err)
	}
}
