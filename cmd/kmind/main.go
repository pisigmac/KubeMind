package main

import (
	"fmt"
	"os"

	"github.com/kubemind/kmind/commands"
	"github.com/kubemind/kmind/internal"
)

func main() {
	if len(os.Args) < 2 {
		commands.PrintUsage()
		os.Exit(0)
	}

	cmd := os.Args[1]
	switch cmd {
	case "help", "-h", "--help":
		commands.PrintUsage()
		return
	case "init":
		// init does not require an existing config
		commands.Init(nil)
		return
	}

	cfg, err := internal.LoadConfig()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading config: %v\n", err)
		os.Exit(1)
	}

	switch cmd {
	case "up":
		commands.Up(cfg)
	case "down":
		commands.Down(cfg)
	case "status":
		commands.Status(cfg)
	case "top", "monitor":
		commands.Top(cfg, os.Args[2:])
	case "chat":
		commands.Chat(cfg, os.Args[2:])
	case "analytics":
		commands.Analytics(cfg, os.Args[2:])
	case "verify":
		commands.Verify(cfg, os.Args[2:])
	case "mcp":
		commands.MCP(cfg, os.Args[2:])
	case "red-team", "redteam":
		commands.RedTeam(cfg, os.Args[2:])
	case "agent":
		commands.Agent(cfg, os.Args[2:])
	case "knowledge":
		commands.Knowledge(cfg, os.Args[2:])
	case "gateway":
		commands.Gateway(cfg, os.Args[2:])
	case "trace":
		commands.Trace(cfg, os.Args[2:])
	case "logs":
		commands.Logs(cfg, os.Args[2:])
	default:
		fmt.Fprintf(os.Stderr, "Unknown command: %s\n", cmd)
		commands.PrintUsage()
		os.Exit(1)
	}
}
