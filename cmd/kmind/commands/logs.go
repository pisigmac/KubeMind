package commands

import (
	"os"
	"os/exec"

	"github.com/kubemind/kmind/internal"
)

func Logs(cfg *internal.Config, args []string) {
	service := ""
	if len(args) > 0 {
		service = args[0]
	}

	cmd := exec.Command("docker", "compose", "logs", "-f", service)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Dir = findComposeDir()
	_ = cmd.Run()
}
