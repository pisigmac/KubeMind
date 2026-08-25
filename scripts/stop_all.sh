#!/usr/bin/env bash
# ==============================================================================
# KubeMind Stack Shutdown Utility
#
# Cleanly stops all KubeMind containers, frees bound network ports, and cleans
# up background processes.
#
# Usage:
#   ./scripts/stop_all.sh [OPTIONS]
# Options:
#   --volumes, -v   Wipe persistent Docker volumes (Postgres, Redis data)
#   --force, -f     Force kill any lingering processes on ports
#   --help, -h      Show this help message
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

WIPE_VOLUMES=0
FORCE_KILL=0

for arg in "$@"; do
  case "$arg" in
    --volumes|-v)
      WIPE_VOLUMES=1
      ;;
    --force|-f)
      FORCE_KILL=1
      ;;
    --help|-h)
      echo -e "${BOLD}Usage:${NC} ./scripts/stop_all.sh [OPTIONS]"
      echo ""
      echo -e "${BOLD}Options:${NC}"
      echo "  --volumes, -v   Remove named data volumes (wipes Postgres, Redis data)"
      echo "  --force, -f     Force-kill any lingering process bound to KubeMind ports"
      echo "  --help, -h      Show this help message"
      exit 0
      ;;
  esac
done

cd "$ROOT_DIR"

echo -e "\n${YELLOW}${BOLD}====================================================================${NC}"
echo -e "${YELLOW}${BOLD}        🛑 Stopping KubeMind AI Control Plane Stack                 ${NC}"
echo -e "${YELLOW}${BOLD}====================================================================${NC}\n"

# 1. Stop Docker Compose
VOL_FLAG=""
if [[ $WIPE_VOLUMES -eq 1 ]]; then
  echo -e "  ${CYAN}[1/3] Stopping containers & removing data volumes (-v)...${NC}"
  VOL_FLAG="-v"
else
  echo -e "  ${CYAN}[1/3] Stopping and removing containers...${NC}"
fi

docker compose down $VOL_FLAG --remove-orphans >/dev/null 2>&1 || true
echo -e "    ${GREEN}✓ Docker Compose services stopped.${NC}"

# 2. Check for lingering orphaned processes on KubeMind ports
echo -e "  ${CYAN}[2/3] Checking for orphaned port listeners...${NC}"
PORTS=(9080 9081 9082 9083 9000 9432 9379 9434)
FOUND_ORPHAN=0

for p in "${PORTS[@]}"; do
  PIDS=$(lsof -Pi :"$p" -sTCP:LISTEN -t 2>/dev/null || true)
  if [[ -n "$PIDS" ]]; then
    FOUND_ORPHAN=1
    echo -e "    ${YELLOW}⚠ Found process listening on port $p (PID: $PIDS)${NC}"
    if [[ $FORCE_KILL -eq 1 ]]; then
      echo -e "      ${RED}Force killing PID $PIDS...${NC}"
      kill -9 $PIDS 2>/dev/null || true
    fi
  fi
done

if [[ $FOUND_ORPHAN -eq 0 ]]; then
  echo -e "    ${GREEN}✓ All KubeMind ports (9080-9083, 9000, 9432, 9379) are free.${NC}"
elif [[ $FORCE_KILL -eq 0 ]]; then
  echo -e "    ${YELLOW}ℹ Use ./scripts/stop_all.sh --force to terminate orphaned PIDs if needed.${NC}"
fi

# 3. Clean temporary PID files and dangling containers
echo -e "  ${CYAN}[3/3] Cleaning up temporary runfiles...${NC}"
rm -f /tmp/kubemind_*.pid 2>/dev/null || true

echo -e "\n${GREEN}${BOLD}====================================================================${NC}"
echo -e "${GREEN}${BOLD}        ✅ KubeMind Stack is completely shut down.                  ${NC}"
echo -e "${GREEN}${BOLD}====================================================================${NC}\n"
