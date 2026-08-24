package commands

import (
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"

	"github.com/kubemind/kmind/internal"
)

const (
	DefaultONNXModelURL = "https://huggingface.co/dslim/bert-base-NER-onnx/resolve/main/model.onnx"
	ModelDirName        = ".kubemind/models"
)

func FetchModels(cfg *internal.Config, args []string) {
	fs := flag.NewFlagSet("fetch-models", flag.ContinueOnError)
	modelURL := fs.String("url", "", "Custom ONNX model download URL")
	force := fs.Bool("force", false, "Overwrite existing model file")
	fs.BoolVar(force, "f", false, "Overwrite existing model file (shorthand)")

	if err := fs.Parse(args); err != nil {
		fmt.Fprintf(os.Stderr, "Error parsing flags: %v\n", err)
		return
	}

	home, err := os.UserHomeDir()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to determine user home directory: %v\n", err)
		return
	}

	targetDir := filepath.Join(home, ModelDirName)
	if err := os.MkdirAll(targetDir, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create model directory %s: %v\n", targetDir, err)
		return
	}

	targetPath := filepath.Join(targetDir, "ner-bert-base.onnx")
	if _, err := os.Stat(targetPath); err == nil && !*force {
		fmt.Printf("✅ Model already exists at %s (use --force to redownload)\n", targetPath)
		fmt.Printf("💡 Export: export KUBEMIND_NER_ONNX_MODEL_PATH=\"%s\"\n", targetPath)
		return
	}

	url := DefaultONNXModelURL
	if *modelURL != "" {
		url = *modelURL
	}

	fmt.Printf("📥 Fetching ONNX NER model from %s...\n", url)
	resp, err := http.Get(url)
	if err != nil {
		fmt.Fprintf(os.Stderr, "HTTP request failed: %v\n", err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		fmt.Fprintf(os.Stderr, "Download failed with HTTP status %s\n", resp.Status)
		return
	}

	out, err := os.Create(targetPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create target file: %v\n", err)
		return
	}
	defer out.Close()

	n, err := io.Copy(out, resp.Body)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to save model file: %v\n", err)
		return
	}

	fmt.Printf("✅ Downloaded ONNX model (%.2f MB) to %s\n", float64(n)/(1024*1024), targetPath)
	fmt.Printf("💡 Export: export KUBEMIND_NER_ONNX_MODEL_PATH=\"%s\"\n", targetPath)
}
