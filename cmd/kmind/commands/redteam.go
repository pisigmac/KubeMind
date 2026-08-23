package commands

import (
	"fmt"
	"os"
	"os/exec"

	"github.com/kubemind/kmind/internal"
)

func RedTeam(cfg *internal.Config, args []string) {
	fmt.Println("🛡️ Executing KubeMind Automated Adversarial Red-Team Simulator...")

	cmd := exec.Command("python3", "eval/red_team.py")
	cmd.Dir = "services/router"
	cmd.Env = append(os.Environ(), "PYTHONPATH=../../shared/python:$PYTHONPATH")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "Red-team audit execution failed: %v\n", err)
	}
}
