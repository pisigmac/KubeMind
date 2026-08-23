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

func Chat(cfg *internal.Config, args []string) {
	model := "llama3.1"
	if len(args) > 0 {
		model = args[0]
	}

	fmt.Println("====================================================================")
	fmt.Printf("🚀 KubeMind Interactive Streaming REPL (Model: %s)\n", model)
	fmt.Println("Type your prompt and press Enter. Type 'exit' or 'quit' to end.")
	fmt.Println("====================================================================")

	reader := bufio.NewReader(os.Stdin)
	var history []ChatMessage

	for {
		fmt.Print("\n\033[1;34mkmind>\033[0m ")
		input, err := reader.ReadString('\n')
		if err != nil {
			break
		}

		input = strings.TrimSpace(input)
		if input == "" {
			continue
		}
		if input == "exit" || input == "quit" {
			fmt.Println("Goodbye!")
			break
		}

		history = append(history, ChatMessage{Role: "user", Content: input})

		payload := ChatPayload{
			Model:       model,
			Messages:    history,
			Stream:      true,
			EnableCache: true,
		}

		bodyBytes, err := json.Marshal(payload)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error serializing payload: %v\n", err)
			continue
		}

		req, err := http.NewRequest("POST", cfg.GatewayEndpoint+"/v1/chat/completions", bytes.NewReader(bodyBytes))
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error creating request: %v\n", err)
			continue
		}

		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-Workspace-ID", cfg.Workspace.ID)
		if cfg.Workspace.APIKey != "" {
			req.Header.Set("X-API-Key", cfg.Workspace.APIKey)
		}

		client := &http.Client{}
		resp, err := client.Do(req)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error connecting to gateway: %v\n", err)
			continue
		}

		if resp.StatusCode >= 400 {
			errData, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			fmt.Printf("\033[1;31mError (%d):\033[0m %s\n", resp.StatusCode, string(errData))
			continue
		}

		fmt.Print("\033[1;32massistant>\033[0m ")
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
						delta := chunk.Choices[0].Delta.Content
						if delta != "" {
							fmt.Print(delta)
							fullReply.WriteString(delta)
						}
					}
				}
			}
		}
		resp.Body.Close()
		fmt.Println()

		history = append(history, ChatMessage{Role: "assistant", Content: fullReply.String()})
	}
}
