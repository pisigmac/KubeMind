#!/usr/bin/env bash
# ==============================================================================
# KubeMind Stack Restart Utility
#
# Performs a clean stop followed by a start with full argument forwarding.
#
# Usage:
#   ./scripts/restart_all.sh [OPTIONS]
#   Supports all options from start_all.sh (--build, --seed, etc.)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "Restarting KubeMind Stack..."
bash "${SCRIPT_DIR}/stop_all.sh"
sleep 2
bash "${SCRIPT_DIR}/start_all.sh" "$@"
