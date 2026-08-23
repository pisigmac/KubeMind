package commands

import "fmt"

func PrintUsage() {
	fmt.Println(`KubeMind — Kubernetes-native AI operating infrastructure

Usage: kmind <command> [args...]

Commands:
  init              Create ~/.kmind/config.yaml
  up                Start all services (docker compose up)
  down              Stop all services
  status            Check health of all services
  top               Live real-time terminal TUI cluster monitor
  chat [model]      Interactive real-time streaming REPL
  logs [service]    Tail logs for a service

  analytics [hours] Show CFO-level token usage and spend breakdown (default: 24h)
  verify            Cryptographically verify the Sentinel SHA-256 audit ledger
  mcp               Start Model Context Protocol (MCP) JSON-RPC server for Cursor/Claude

  agent run "<prompt>"     Run a one-shot mission
  agent repl               Interactive agent session
  agent list               List active missions

  knowledge ingest <path|url>   Ingest into knowledge graph
  knowledge query "<query>"     Search knowledge graph
  knowledge nodes <id>          Inspect a node

  gateway usage            Show cost/token summary
  gateway providers        Show provider health
  gateway cache-clear      Clear response cache

  trace live               Open observability dashboard
  trace export             Export local traces

  help                     Show this message`)
}
