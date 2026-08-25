package commands

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/kubemind/kmind/internal"
)

type StreamChunk struct {
	ID      string `json:"id"`
	Model   string `json:"model"`
	Choices []struct {
		Index int `json:"index"`
		Delta struct {
			Content string `json:"content"`
			Role    string `json:"role"`
		} `json:"delta"`
		FinishReason *string `json:"finish_reason"`
	} `json:"choices"`
}

type ChatPayload struct {
	Model       string        `json:"model"`
	Messages    []ChatMessage `json:"messages"`
	Stream      bool          `json:"stream"`
	EnableCache bool          `json:"enable_cache"`
}

type ChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// ANSI Color Palette
const (
	colorReset   = "\033[0m"
	colorBold    = "\033[1m"
	colorDim     = "\033[2m"
	colorBlue    = "\033[1;34m"
	colorGreen   = "\033[1;32m"
	colorYellow  = "\033[1;33m"
	colorCyan    = "\033[1;36m"
	colorRed     = "\033[1;31m"
	colorMagenta = "\033[1;35m"
	colorGray    = "\033[0;90m"
)

func Chat(cfg *internal.Config, args []string) {
	activeModel := "auto"
	if len(args) > 0 {
		activeModel = args[0]
	}

	printBanner(cfg, activeModel)

	reader := bufio.NewReader(os.Stdin)
	var history []ChatMessage

	for {
		fmt.Printf("\n%s[%s|%s]%s %skmind>%s ", colorCyan, cfg.Workspace.ID, activeModel, colorReset, colorBlue, colorReset)
		input, err := reader.ReadString('\n')
		if err != nil {
			fmt.Println("\nExiting session. Goodbye!")
			break
		}

		input = strings.TrimSpace(input)
		if input == "" {
			continue
		}

		// Handle Slash Commands and Keywords
		if strings.HasPrefix(input, "/") || isKeywordCommand(input) {
			handled, shouldExit := handleCommand(input, cfg, &activeModel, &history, reader)
			if shouldExit {
				fmt.Println("Exiting session. Goodbye!")
				break
			}
			if handled {
				continue
			}
		}

		// Execute chat completion request
		history = append(history, ChatMessage{Role: "user", Content: input})
		reply, err := executeChatStream(cfg, activeModel, history)
		if err != nil {
			fmt.Printf("%s[Error]%s %v\n", colorRed, colorReset, err)
			// Remove failed user turn from history to keep context clean
			if len(history) > 0 {
				history = history[:len(history)-1]
			}
			continue
		}

		if reply != "" {
			history = append(history, ChatMessage{Role: "assistant", Content: reply})
		}
	}
}

func printBanner(cfg *internal.Config, model string) {
	fmt.Println(colorBlue + "====================================================================" + colorReset)
	fmt.Printf("%s🧠 KubeMind Enterprise Interactive Terminal REPL%s\n", colorBold, colorReset)
	fmt.Printf("   %sGateway:%s   %s\n", colorGray, colorReset, cfg.GatewayEndpoint)
	fmt.Printf("   %sWorkspace:%s %s  %s(Key: %s)%s\n", colorGray, colorReset, cfg.Workspace.ID, colorDim, maskKey(cfg.Workspace.APIKey), colorReset)
	fmt.Printf("   %sModel:%s     %s%s%s (auto-intent routing enabled)\n", colorGray, colorReset, colorGreen, model, colorReset)
	fmt.Printf("   %sCommands:%s  Type %s/help%s for options (%s/login, /config, /model, /rag, /status%s)\n", colorGray, colorReset, colorCyan, colorReset, colorDim, colorReset)
	fmt.Println(colorBlue + "====================================================================" + colorReset)
}

func isKeywordCommand(input string) bool {
	lower := strings.ToLower(input)
	return lower == "exit" || lower == "quit" || lower == "q" || lower == ":q" ||
		lower == "help" || lower == "clear" || lower == "status" || lower == "history"
}

func handleCommand(cmd string, cfg *internal.Config, activeModel *string, history *[]ChatMessage, reader *bufio.Reader) (bool, bool) {
	cmd = strings.TrimPrefix(cmd, "/")
	parts := strings.Fields(cmd)
	if len(parts) == 0 {
		return true, false
	}

	action := strings.ToLower(parts[0])
	args := parts[1:]

	switch action {
	case "exit", "quit", "q", ":q":
		return true, true

	case "help", "?":
		printHelp()
		return true, false

	case "clear", "cls":
		fmt.Print("\033[H\033[2J")
		fmt.Printf("%s[Screen cleared]%s (Conversation memory preserved: %d turns)\n", colorGray, colorReset, len(*history)/2)
		return true, false

	case "reset":
		*history = []ChatMessage{}
		fmt.Printf("%s✓ Conversation history reset.%s\n", colorGreen, colorReset)
		return true, false

	case "history":
		printHistory(*history)
		return true, false

	case "login", "auth":
		handleLogin(cfg, reader)
		return true, false

	case "config":
		handleConfig(cfg, args, reader)
		return true, false

	case "model", "models":
		handleModel(cfg, activeModel, args)
		return true, false

	case "workspace", "ws":
		handleWorkspace(cfg, args, history)
		return true, false

	case "status":
		handleStatus(cfg)
		return true, false

	case "verify", "ledger":
		handleVerify(cfg)
		return true, false

	case "rag", "mind", "knowledge":
		handleRag(cfg, args)
		return true, false

	default:
		fmt.Printf("%sUnknown command:%s /%s. Type %s/help%s for available options.\n", colorYellow, colorReset, action, colorCyan, colorReset)
		return true, false
	}
}

func printHelp() {
	fmt.Println(colorCyan + "\n── Interactive REPL Command Reference ──────────────────────────────" + colorReset)
	fmt.Printf("  %s/login%s                 Authenticate workspace & update credentials\n", colorBold, colorReset)
	fmt.Printf("  %s/config [show|set|save]%s Inspect or edit active cluster configuration\n", colorBold, colorReset)
	fmt.Printf("  %s/model [name]%s          Switch active LLM (e.g. gpt-4o, claude-3-5, llama3.1, auto)\n", colorBold, colorReset)
	fmt.Printf("  %s/models%s                List all available upstream & local models\n", colorBold, colorReset)
	fmt.Printf("  %s/workspace [id]%s        Switch tenant workspace scope\n", colorBold, colorReset)
	fmt.Printf("  %s/rag <query>%s           Search Mind knowledge graph directly\n", colorBold, colorReset)
	fmt.Printf("  %s/status%s                Run cluster health & latency diagnostics\n", colorBold, colorReset)
	fmt.Printf("  %s/verify%s                Verify cryptographic SHA-256 audit ledger\n", colorBold, colorReset)
	fmt.Printf("  %s/history%s               View current conversation turns & message count\n", colorBold, colorReset)
	fmt.Printf("  %s/reset%s                 Clear conversation context memory\n", colorBold, colorReset)
	fmt.Printf("  %s/clear%s                 Clear terminal screen\n", colorBold, colorReset)
	fmt.Printf("  %s/quit, /exit, q%s        Exit the interactive REPL\n", colorBold, colorReset)
	fmt.Println(colorCyan + "────────────────────────────────────────────────────────────────────" + colorReset)
}

func handleLogin(cfg *internal.Config, reader *bufio.Reader) {
	fmt.Println(colorCyan + "\n🔑 KubeMind Workspace Authentication" + colorReset)

	fmt.Printf("Enter Workspace ID [%s%s%s]: ", colorGreen, cfg.Workspace.ID, colorReset)
	wsInput, _ := reader.ReadString('\n')
	wsInput = strings.TrimSpace(wsInput)
	if wsInput != "" {
		cfg.Workspace.ID = wsInput
	}

	fmt.Printf("Enter API Key / Token [%s]: ", maskKey(cfg.Workspace.APIKey))
	keyInput, _ := reader.ReadString('\n')
	keyInput = strings.TrimSpace(keyInput)
	if keyInput != "" {
		cfg.Workspace.APIKey = keyInput
	}

	// Test authentication
	fmt.Printf("%sTesting authentication with gateway...%s ", colorGray, colorReset)
	client := &http.Client{Timeout: 5 * time.Second}
	req, _ := http.NewRequest("GET", cfg.GatewayEndpoint+"/health", nil)
	req.Header.Set("X-Workspace-ID", cfg.Workspace.ID)
	if cfg.Workspace.APIKey != "" {
		req.Header.Set("X-API-Key", cfg.Workspace.APIKey)
	}

	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("%s[Warning: Gateway unreachable: %v]%s\n", colorYellow, err, colorReset)
	} else {
		resp.Body.Close()
		if resp.StatusCode == 200 {
			fmt.Printf("%s[Connection Verified OK]%s\n", colorGreen, colorReset)
		} else {
			fmt.Printf("%s[Gateway responded HTTP %d]%s\n", colorYellow, resp.StatusCode, colorReset)
		}
	}

	if err := cfg.Save(); err != nil {
		fmt.Printf("%sError saving to ~/.kmind/config.yaml: %v%s\n", colorRed, err, colorReset)
	} else {
		fmt.Printf("%s✓ Credentials saved to ~/.kmind/config.yaml (Workspace: %s)%s\n", colorGreen, cfg.Workspace.ID, colorReset)
	}
}

func handleConfig(cfg *internal.Config, args []string, reader *bufio.Reader) {
	if len(args) == 0 || args[0] == "show" || args[0] == "list" {
		fmt.Println(colorCyan + "\n── Active Configuration ────────────────────────────────────────────" + colorReset)
		fmt.Printf("  • %-20s %s\n", "Gateway Endpoint:", cfg.GatewayEndpoint)
		fmt.Printf("  • %-20s %s\n", "Knowledge (Mind):", cfg.KnowledgeEndpoint)
		fmt.Printf("  • %-20s %s\n", "Agent Swarm:", cfg.APIEndpoint)
		fmt.Printf("  • %-20s %s\n", "Sentinel Tracer:", cfg.TraceEndpoint)
		fmt.Printf("  • %-20s %s\n", "Dashboard Console:", cfg.DashboardURL)
		fmt.Printf("  • %-20s %s\n", "Workspace ID:", cfg.Workspace.ID)
		fmt.Printf("  • %-20s %s\n", "API Key:", maskKey(cfg.Workspace.APIKey))
		fmt.Println(colorCyan + "────────────────────────────────────────────────────────────────────" + colorReset)
		fmt.Printf("  %sUsage:%s /config set <key> <value>   (keys: gateway, mind, agents, sentinel, workspace, key)\n", colorDim, colorReset)
		return
	}

	if args[0] == "set" && len(args) >= 3 {
		key := strings.ToLower(args[1])
		val := args[2]

		switch key {
		case "gateway", "router":
			cfg.GatewayEndpoint = strings.TrimRight(val, "/")
		case "mind", "knowledge":
			cfg.KnowledgeEndpoint = strings.TrimRight(val, "/")
		case "agent", "agents", "api":
			cfg.APIEndpoint = strings.TrimRight(val, "/")
		case "sentinel", "trace":
			cfg.TraceEndpoint = strings.TrimRight(val, "/")
		case "dashboard":
			cfg.DashboardURL = strings.TrimRight(val, "/")
		case "workspace", "ws":
			cfg.Workspace.ID = val
		case "key", "apikey", "api_key":
			cfg.Workspace.APIKey = val
		default:
			fmt.Printf("%sUnknown config key:%s %s\n", colorRed, colorReset, key)
			return
		}

		if err := cfg.Save(); err != nil {
			fmt.Printf("%sError saving config: %v%s\n", colorRed, err, colorReset)
		} else {
			fmt.Printf("%s✓ Updated %s = %s and saved to config.%s\n", colorGreen, key, val, colorReset)
		}
		return
	}

	if args[0] == "save" {
		if err := cfg.Save(); err != nil {
			fmt.Printf("%sError saving: %v%s\n", colorRed, err, colorReset)
		} else {
			fmt.Printf("%s✓ Config saved to ~/.kmind/config.yaml%s\n", colorGreen, colorReset)
		}
		return
	}

	fmt.Printf("%sInvalid config command. Usage: /config [show|set <key> <val>|save]%s\n", colorYellow, colorReset)
}

func handleModel(cfg *internal.Config, activeModel *string, args []string) {
	if len(args) > 0 {
		*activeModel = args[0]
		fmt.Printf("%s✓ Active model set to: %s%s%s\n", colorGreen, colorBold, *activeModel, colorReset)
		return
	}

	fmt.Printf("\n  Current Model: %s%s%s\n", colorGreen, *activeModel, colorReset)
	fmt.Printf("%sFetching available models from gateway...%s\n", colorGray, colorReset)

	client := &http.Client{Timeout: 5 * time.Second}
	req, _ := http.NewRequest("GET", cfg.GatewayEndpoint+"/v1/models", nil)
	req.Header.Set("X-Workspace-ID", cfg.Workspace.ID)
	if cfg.Workspace.APIKey != "" {
		req.Header.Set("X-API-Key", cfg.Workspace.APIKey)
	}

	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("  %sGateway unreachable. Using local aliases: auto, llama3.1, gpt-4o, claude-3-5-sonnet, deepseek-r1%s\n", colorYellow, colorReset)
		return
	}
	defer resp.Body.Close()

	var data struct {
		Data []struct {
			ID      string `json:"id"`
			OwnedBy string `json:"owned_by"`
		} `json:"data"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&data); err == nil && len(data.Data) > 0 {
		fmt.Println(colorCyan + "── Available Models ────────────────────────────────────────────────" + colorReset)
		for _, m := range data.Data {
			prefix := "  "
			if m.ID == *activeModel {
				prefix = colorGreen + "▶ "
			}
			fmt.Printf("%s%-30s %s(provider: %s)%s\n", prefix, m.ID, colorDim, m.OwnedBy, colorReset)
		}
		fmt.Println(colorCyan + "────────────────────────────────────────────────────────────────────" + colorReset)
		fmt.Printf("  %sSwitch model using:%s /model <name>\n", colorDim, colorReset)
	} else {
		fmt.Println("  Supported profiles: auto, llama3.1, gpt-4o, gpt-4o-mini, claude-3-5-sonnet, deepseek-r1")
	}
}

func handleWorkspace(cfg *internal.Config, args []string, history *[]ChatMessage) {
	if len(args) == 0 {
		fmt.Printf("Current Workspace: %s%s%s\n", colorGreen, cfg.Workspace.ID, colorReset)
		return
	}
	newWS := args[0]
	cfg.Workspace.ID = newWS
	*history = []ChatMessage{}
	fmt.Printf("%s✓ Switched workspace to: %s (Context history reset)%s\n", colorGreen, newWS, colorReset)
}

func handleRag(cfg *internal.Config, args []string) {
	if len(args) == 0 {
		fmt.Println("Usage: /rag <search query>")
		return
	}
	query := strings.Join(args, " ")
	fmt.Printf("%sSearching Mind knowledge graph for:%s \"%s\"...\n", colorGray, colorReset, query)

	payload := map[string]any{
		"query": query,
		"top_k": 3,
	}
	bodyBytes, _ := json.Marshal(payload)

	client := &http.Client{Timeout: 10 * time.Second}
	req, _ := http.NewRequest("POST", cfg.KnowledgeEndpoint+"/v1/query", bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Workspace-ID", cfg.Workspace.ID)
	if cfg.Workspace.APIKey != "" {
		req.Header.Set("X-API-Key", cfg.Workspace.APIKey)
	}

	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("%sError querying Mind: %v%s\n", colorRed, err, colorReset)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		data, _ := io.ReadAll(resp.Body)
		fmt.Printf("%sMind error (%d): %s%s\n", colorRed, resp.StatusCode, string(data), colorReset)
		return
	}

	var results struct {
		Nodes []struct {
			ID       string  `json:"id"`
			Score    float64 `json:"score"`
			Title    string  `json:"title"`
			Content  string  `json:"content"`
			NodeType string  `json:"node_type"`
		} `json:"nodes"`
	}

	json.NewDecoder(resp.Body).Decode(&results)
	if len(results.Nodes) == 0 {
		fmt.Println("  No matching documents found in workspace knowledge graph.")
		return
	}

	fmt.Println(colorCyan + "\n── Matched Knowledge Nodes ─────────────────────────────────────────" + colorReset)
	for i, n := range results.Nodes {
		snippet := n.Content
		if len(snippet) > 140 {
			snippet = snippet[:140] + "..."
		}
		fmt.Printf("  [%d] %s%s%s (Score: %.2f, Type: %s)\n      %s%s%s\n", i+1, colorBold, n.Title, colorReset, n.Score, n.NodeType, colorDim, snippet, colorReset)
	}
	fmt.Println(colorCyan + "────────────────────────────────────────────────────────────────────" + colorReset)
}

func handleStatus(cfg *internal.Config) {
	fmt.Println(colorCyan + "\n── KubeMind Stack Diagnostics ──────────────────────────────────────" + colorReset)
	pingService("Router Gateway", cfg.GatewayEndpoint+"/health", cfg)
	pingService("Mind Knowledge", cfg.KnowledgeEndpoint+"/health", cfg)
	pingService("Agents Swarm", cfg.APIEndpoint+"/health", cfg)
	pingService("Sentinel Tracer", cfg.TraceEndpoint+"/health", cfg)
	fmt.Println(colorCyan + "────────────────────────────────────────────────────────────────────" + colorReset)
}

func pingService(name, url string, cfg *internal.Config) {
	start := time.Now()
	client := &http.Client{Timeout: 3 * time.Second}
	req, _ := http.NewRequest("GET", url, nil)
	req.Header.Set("X-Workspace-ID", cfg.Workspace.ID)
	if cfg.Workspace.APIKey != "" {
		req.Header.Set("X-API-Key", cfg.Workspace.APIKey)
	}

	resp, err := client.Do(req)
	latency := time.Since(start).Milliseconds()
	if err != nil || resp.StatusCode >= 400 {
		fmt.Printf("  • %-20s %s[OFFLINE]%s (URL: %s)\n", name, colorRed, colorReset, url)
	} else {
		resp.Body.Close()
		fmt.Printf("  • %-20s %s[ONLINE]%s  (%dms · %s)\n", name, colorGreen, colorReset, latency, url)
	}
}

func handleVerify(cfg *internal.Config) {
	fmt.Println(colorCyan + "\n── Cryptographic SHA-256 Ledger Audit ──────────────────────────────" + colorReset)
	client := &http.Client{Timeout: 5 * time.Second}
	url := fmt.Sprintf("%s/v1/audit/verify?workspace_id=%s&limit=10", cfg.TraceEndpoint, cfg.Workspace.ID)
	req, _ := http.NewRequest("GET", url, nil)
	req.Header.Set("X-Workspace-ID", cfg.Workspace.ID)
	if cfg.Workspace.APIKey != "" {
		req.Header.Set("X-API-Key", cfg.Workspace.APIKey)
	}

	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("  %sError contacting Sentinel: %v%s\n", colorRed, err, colorReset)
		return
	}
	defer resp.Body.Close()

	var verifyResp struct {
		WorkspaceID    string `json:"workspace_id"`
		Valid          bool   `json:"valid"`
		Verified       bool   `json:"verified"`
		EntriesChecked int    `json:"entries_checked"`
		HeadHash       string `json:"head_hash"`
		Detail         string `json:"detail"`
	}

	json.NewDecoder(resp.Body).Decode(&verifyResp)
	isValid := verifyResp.Valid || verifyResp.Verified

	if isValid {
		fmt.Printf("  %s✓ SHA-256 Ledger Verified Intact%s\n", colorGreen, colorReset)
		fmt.Printf("    • Blocks Checked: %d\n", verifyResp.EntriesChecked)
		if verifyResp.HeadHash != "" {
			fmt.Printf("    • Head SHA-256:   %s\n", verifyResp.HeadHash)
		}
	} else {
		fmt.Printf("  %s❌ Ledger Verification Failed: %s%s\n", colorRed, verifyResp.Detail, colorReset)
	}
	fmt.Println(colorCyan + "────────────────────────────────────────────────────────────────────" + colorReset)
}

func printHistory(history []ChatMessage) {
	fmt.Println(colorCyan + "\n── Session Context History ─────────────────────────────────────────" + colorReset)
	if len(history) == 0 {
		fmt.Println("  (No conversation history in current session)")
		return
	}
	for i, m := range history {
		roleColor := colorGreen
		if m.Role == "user" {
			roleColor = colorBlue
		}
		snippet := m.Content
		if len(snippet) > 80 {
			snippet = snippet[:80] + "..."
		}
		fmt.Printf("  [%d] %s%s%s: %s\n", i+1, roleColor, m.Role, colorReset, snippet)
	}
	fmt.Printf("  Total turns: %d | Tokens preserved inline.\n", len(history)/2)
	fmt.Println(colorCyan + "────────────────────────────────────────────────────────────────────" + colorReset)
}

func executeChatStream(cfg *internal.Config, model string, history []ChatMessage) (string, error) {
	payload := ChatPayload{
		Model:       model,
		Messages:    history,
		Stream:      true,
		EnableCache: true,
	}

	bodyBytes, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("error serializing payload: %w", err)
	}

	req, err := http.NewRequest("POST", cfg.GatewayEndpoint+"/v1/chat/completions", bytes.NewReader(bodyBytes))
	if err != nil {
		return "", fmt.Errorf("error creating request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Workspace-ID", cfg.Workspace.ID)
	if cfg.Workspace.APIKey != "" {
		req.Header.Set("X-API-Key", cfg.Workspace.APIKey)
	}

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("error connecting to gateway (%s): %w", cfg.GatewayEndpoint, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		errData, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("gateway HTTP %d: %s", resp.StatusCode, string(errData))
	}

	fmt.Printf("%sassistant>%s ", colorGreen, colorReset)
	var fullReply strings.Builder
	scanner := bufio.NewScanner(resp.Body)

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if strings.HasPrefix(line, "data: ") {
			dataStr := strings.TrimPrefix(line, "data: ")
			if dataStr == "[DONE]" {
				break
			}

			var chunk StreamChunk
			if err := json.Unmarshal([]byte(dataStr), &chunk); err == nil {
				if len(chunk.Choices) > 0 {
					content := chunk.Choices[0].Delta.Content
					fmt.Print(content)
					fullReply.WriteString(content)
				}
			}
		}
	}

	fmt.Println()
	return fullReply.String(), nil
}

func maskKey(key string) string {
	if key == "" {
		return "<none>"
	}
	if len(key) <= 8 {
		return "••••••••"
	}
	return key[:4] + "••••" + key[len(key)-4:]
}
