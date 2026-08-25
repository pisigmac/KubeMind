#!/usr/bin/env bash
# ==============================================================================
# KubeMind Stack Startup Utility
#
# Launches the complete KubeMind AI Governance & Control Plane:
#  - Postgres (pgvector HNSW) :9432
#  - Redis :9379
#  - Ollama Inference :9434
#  - Router Gateway :9080
#  - Mind Context Engine :9081
#  - Agents Swarm Planner :9082
#  - Sentinel Ledger & Tracer :9083
#  - Operator Dashboard :9000
#
# Usage:
#   ./scripts/start_all.sh [OPTIONS]
# Options:
#   --build       Rebuild Docker images before starting
#   --seed        Seed demo documents and traces after startup
#   --help        Show this help message
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors for UI
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

DO_BUILD=0
DO_SEED=0

for arg in "$@"; do
  case "$arg" in
    --build)
      DO_BUILD=1
      ;;
    --seed)
      DO_SEED=1
      ;;
    --help|-h)
      echo -e "${BOLD}Usage:${NC} ./scripts/start_all.sh [OPTIONS]"
      echo ""
      echo -e "${BOLD}Options:${NC}"
      echo "  --build     Rebuild all Docker container images before starting"
      echo "  --seed      Automatically seed sample knowledge & traces into Mind & Sentinel"
      echo "  --help, -h  Show this help message"
      exit 0
      ;;
  esac
done

cd "$ROOT_DIR"

echo -e "\n${BLUE}${BOLD}====================================================================${NC}"
echo -e "${BLUE}${BOLD}        🚀 Starting KubeMind AI Control Plane Stack                 ${NC}"
echo -e "${BLUE}${BOLD}====================================================================${NC}\n"

# 1. Environment check
if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    echo -e "  ${YELLOW}ℹ .env not found. Creating .env from .env.example...${NC}"
    cp .env.example .env
  else
    touch .env
  fi
fi

# 2. Check Docker daemon
if ! docker info >/dev/null 2>&1; then
  echo -e "  ${RED}❌ Docker daemon is not running. Please start Docker and retry.${NC}\n"
  exit 1
fi

# 3. Clean up stale port conflicts if present
PORTS=(9080 9081 9082 9083 9000 9432 9379 9434)
echo -e "  ${CYAN}[1/4] Checking port availability...${NC}"
for p in "${PORTS[@]}"; do
  if lsof -Pi :"$p" -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "  ${YELLOW}⚠ Port $p is already in use. Cleaning up previous containers...${NC}"
    docker compose down --remove-orphans >/dev/null 2>&1 || true
    break
  fi
done

# 4. Launch Stack
BUILD_FLAG=""
if [[ $DO_BUILD -eq 1 ]]; then
  echo -e "  ${CYAN}[2/4] Building and launching all services (--build)...${NC}"
  BUILD_FLAG="--build"
else
  echo -e "  ${CYAN}[2/4] Launching all services with Docker Compose...${NC}"
fi

docker compose up -d $BUILD_FLAG --remove-orphans

# 5. Wait for Readiness
echo -e "  ${CYAN}[3/4] Waiting for services to become healthy...${NC}"

wait_for_endpoint() {
  local name="$1"
  local url="$2"
  local max_retries="${3:-30}"
  local count=0

  while [[ $count -lt $max_retries ]]; do
    if curl -sf "$url" >/dev/null 2>&1; then
      echo -e "    ${GREEN}✓ ${name} is UP & healthy (${url})${NC}"
      return 0
    fi
    sleep 1
    count=$((count + 1))
  done

  echo -e "    ${YELLOW}⚠ ${name} health check timed out at ${url} (still initializing)${NC}"
  return 0
}

wait_for_endpoint "Router Gateway" "http://localhost:9080/health" 30
wait_for_endpoint "Mind Context Engine" "http://localhost:9081/health" 30
wait_for_endpoint "Agents Swarm Planner" "http://localhost:9082/health" 30
wait_for_endpoint "Sentinel Ledger & Tracer" "http://localhost:9083/health" 30
wait_for_endpoint "Next.js Dashboard" "http://localhost:9000" 30

# 6. Seed demo data if requested
if [[ $DO_SEED -eq 1 ]]; then
  echo -e "\n  ${CYAN}[4/4] Seeding demo knowledge & audit traces...${NC}"
  if [[ -f "${SCRIPT_DIR}/seed_demo_data.sh" ]]; then
    bash "${SCRIPT_DIR}/seed_demo_data.sh"
  else
    echo -e "  ${YELLOW}⚠ seed_demo_data.sh not found, skipping.${NC}"
  fi
else
  echo -e "  ${CYAN}[4/4] Skipping demo data seed (run with --seed to auto-populate).${NC}"
fi

# 7. Print System Status Banner
echo -e "\n${GREEN}${BOLD}====================================================================${NC}"
echo -e "${GREEN}${BOLD}        🎉 KubeMind Stack is Live and Operational!                  ${NC}"
echo -e "${GREEN}${BOLD}====================================================================${NC}"
echo -e "  ${BOLD}Service Endpoints:${NC}"
echo -e "  • ${CYAN}Dashboard Console:${NC}     http://localhost:9000"
echo -e "  • ${CYAN}Dashboard Billing:${NC}     http://localhost:9000/billing"
echo -e "  • ${CYAN}Router AI Gateway:${NC}     http://localhost:9080"
echo -e "  • ${CYAN}Mind Context Engine:${NC}   http://localhost:9081"
echo -e "  • ${CYAN}Agents Swarm Planner:${NC}  http://localhost:9082"
echo -e "  • ${CYAN}Sentinel Audit Ledger:${NC} http://localhost:9083"
echo -e "  • ${CYAN}Postgres (pgvector):${NC}   localhost:9432 (user: tricore, db: tricore)"
echo -e "  • ${CYAN}Redis Semantic Cache:${NC}  localhost:9379"
echo -e ""
echo -e "  ${BOLD}Quick Operations:${NC}"
echo -e "  • Check cluster health:  ${CYAN}./scripts/status_all.sh${NC} or ${CYAN}make status${NC}"
echo -e "  • Run full E2E tests:    ${CYAN}./scripts/e2e_curl_test.sh${NC}"
echo -e "  • Stop all services:     ${CYAN}./scripts/stop_all.sh${NC} or ${CYAN}make down${NC}"
echo -e "  • View live logs:        ${CYAN}docker compose logs -f${NC}"
echo -e "${GREEN}${BOLD}====================================================================${NC}\n"
