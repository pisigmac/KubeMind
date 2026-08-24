package commands

import (
	"fmt"
	"os"
	"os/exec"

	"github.com/kubemind/kmind/internal"
)

func Up(cfg *internal.Config) {
	cmd := exec.Command("docker", "compose", "up", "-d", "--build")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Dir = findComposeDir()

	if err := cmd.Run(); err != nil {
		fmt.Printf("Error starting services: %v\n", err)
		return
	}
	fmt.Println("KubeMind is starting...")
	fmt.Println("Run `kmind status` to check health")
}

func Down(cfg *internal.Config) {
	cmd := exec.Command("docker", "compose", "down", "-v")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Dir = findComposeDir()
	cmd.Run()
}

func findComposeDir() string {
	// Try to find docker-compose.yml relative to binary
	// In dev, assume current directory
	if _, err := os.Stat("docker-compose.yml"); err == nil {
		return "."
	}
	return "."
}
