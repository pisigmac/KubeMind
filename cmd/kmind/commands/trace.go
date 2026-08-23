package commands

import (
	"fmt"
	"os/exec"
	"runtime"

	"github.com/kubemind/kmind/internal"
)

func Trace(cfg *internal.Config, args []string) {
	if len(args) == 0 {
		fmt.Println("Usage: kmind trace <live|export>")
		return
	}

	switch args[0] {
	case "live":
		url := cfg.DashboardURL + "/observability"
		var cmd *exec.Cmd
		if runtime.GOOS == "darwin" {
			cmd = exec.Command("open", url)
		} else if runtime.GOOS == "linux" {
			cmd = exec.Command("xdg-open", url)
		} else {
			fmt.Printf("Open: %s\n", url)
			return
		}
		cmd.Run()

	case "export":
		client := internal.NewAPIClient(cfg.TraceEndpoint, cfg.Workspace.APIKey, cfg.Workspace.ID)
		resp, err := client.Get("/v1/export")
		if err != nil {
			fmt.Printf("Error: %v\n", err)
			return
		}
		fmt.Println(string(resp))

	default:
		fmt.Printf("Unknown trace command: %s\n", args[0])
	}
}
