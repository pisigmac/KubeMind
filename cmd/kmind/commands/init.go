package commands

import (
	"fmt"

	"github.com/kubemind/kmind/internal"
)

func Init(cfg *internal.Config) {
	defaultCfg := internal.DefaultConfig()
	if err := defaultCfg.Save(); err != nil {
		fmt.Printf("Error saving config: %v\n", err)
		return
	}
	fmt.Println("KubeMind initialized.")
	fmt.Println("Config saved to ~/.kmind/config.yaml")
	fmt.Println("Edit it to match your setup, then run `kmind up`")
}
