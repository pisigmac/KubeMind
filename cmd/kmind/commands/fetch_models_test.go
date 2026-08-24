package commands

import (
	"testing"
)

func TestFetchModelsCommand(t *testing.T) {
	// Verify FetchModels accepts arguments cleanly without crashing
	FetchModels(nil, []string{"-h"})
}
