package main

import (
	"fmt"
	"os"

	"github.com/pisigmac/tricore/commands"
	"github.com/pisigmac/tricore/internal"
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
