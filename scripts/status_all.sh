#!/usr/bin/env bash
# ==============================================================================
# KubeMind Stack Detailed Health & Status Inspector
#
# Inspects every microservice, database, cache, circuit breaker, and audit ledger.
#
# Usage:
#   ./scripts/status_all.sh
# ==============================================================================

set -euo pipefail

ROUTER_URL="${ROUTER_URL:-http://localhost:9080}"
MIND_URL="${MIND_URL:-http://localhost:9081}"
AGENTS_URL="${AGENTS_URL:-http://localhost:9082}"
SENTINEL_URL="${SENTINEL_URL:-http://localhost:9083}"
DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:9000}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "\n${BLUE}${BOLD}====================================================================${NC}"
echo -e "${BLUE}${BOLD}         🔍 KubeMind Cluster Diagnostics & Health Audit             ${NC}"
echo -e "${BLUE}${BOLD}====================================================================${NC}\n"

check_service() {
  local name="$1"
  local url="$2"
  local port="$3"

  local start_time=$(date +%s%N)
  local resp
  resp=$(curl -sf "$url" 2>/dev/null || true)
  local end_time=$(date +%s%N)
  local latency_ms=$(( (end_time - start_time) / 1000000 ))

  if [[ -n "$resp" ]]; then
    echo -e "  [${GREEN}ONLINE${NC}] ${BOLD}${name}${NC} (: ${port})"
    echo -e "           Latency: ${latency_ms}ms · URL: ${url}"
    if echo "$resp" | grep -q "{"; then
      local summary=$(echo "$resp" | python3 -c "import json,sys; d=json.load(sys.stdin); print(', '.join(f'{k}={v}' for k,v in list(d.items())[:3]))" 2>/dev/null || echo "$resp")
      echo -e "           Details: ${CYAN}${summary}${NC}"
    fi
  else
    echo -e "  [${RED}OFFLINE${NC}] ${BOLD}${name}${NC} (: ${port})"
    echo -e "           URL: ${url} (Unreachable)"
  fi
  echo ""
}

# 1. Microservices
echo -e "  ${BOLD}Microservice Health Checks:${NC}"
check_service "Router Gateway" "${ROUTER_URL}/health" "9080"
check_service "Mind Context Engine" "${MIND_URL}/health" "9081"
check_service "Agents Swarm Planner" "${AGENTS_URL}/health" "9082"
check_service "Sentinel Ledger & Tracer" "${SENTINEL_URL}/health" "9083"
check_service "Operator Dashboard" "${DASHBOARD_URL}" "9000"

# 2. Cryptographic Audit Ledger Integrity
echo -e "  ${BOLD}Cryptographic Audit Ledger:${NC}"
LEDGER_RESP=$(curl -sf "${SENTINEL_URL}/v1/audit/verify?workspace_id=default&limit=10" 2>/dev/null || true)
if [[ -n "$LEDGER_RESP" ]]; then
  VERIFIED=$(echo "$LEDGER_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('verified', False))" 2>/dev/null || echo "False")
  ENTRIES=$(echo "$LEDGER_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('entries_checked', 0))" 2>/dev/null || echo "0")
  if [[ "$VERIFIED" == "True" ]]; then
    echo -e "    ${GREEN}✓ SHA-256 Ledger Verified Intact (${ENTRIES} blocks checked)${NC}"
  else
    echo -e "    ${RED}❌ SHA-256 Ledger Verification Failed: ${LEDGER_RESP}${NC}"
  fi
else
  echo -e "    ${YELLOW}⚠ Sentinel ledger offline or unreachable${NC}"
fi

# 3. Upstream Provider Pool
echo -e "\n  ${BOLD}Upstream Provider Circuits:${NC}"
PROV_RESP=$(curl -sf "${ROUTER_URL}/v1/providers/health" 2>/dev/null || true)
if [[ -n "$PROV_RESP" ]]; then
  echo -e "    ${CYAN}${PROV_RESP}${NC}"
else
  echo -e "    ${YELLOW}⚠ Router providers endpoint unreachable${NC}"
fi

# 4. Semantic Cache & Vector Index
echo -e "\n  ${BOLD}Semantic & Exact Cache Stats:${NC}"
CACHE_RESP=$(curl -sf "${ROUTER_URL}/v1/cache/stats" 2>/dev/null || true)
if [[ -n "$CACHE_RESP" ]]; then
  echo -e "    ${CYAN}${CACHE_RESP}${NC}"
else
  echo -e "    ${YELLOW}⚠ Cache stats unavailable${NC}"
fi

echo -e "\n${BLUE}${BOLD}====================================================================${NC}\n"
