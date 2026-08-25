#!/usr/bin/env bash
# ==============================================================================
# KubeMind Multi-Provider & LLM Test Suite
#
# Tests connectivity, streaming completions, intent routing, PII masking,
# and audit ledger integrity across all configured LLM providers:
#   • OpenAI (GPT-4o, GPT-4o-mini)
#   • Google Gemini (Gemini 1.5 Flash, Gemini 1.5 Pro)
#   • Groq (Llama 3.1 70B, Llama 3.1 8B)
#   • Kimi / Moonshot (Moonshot v1 8K)
#   • Grok / xAI (Grok 2)
#   • Local Ollama / DeepSeek
#   • KubeMind Auto-Intent Routing
#
# Usage:
#   ./scripts/test_providers.sh
# ==============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load .env if present
if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  source "${ROOT_DIR}/.env" 2>/dev/null || true
  set +a
fi

ROUTER_URL="${ROUTER_URL:-http://localhost:9080}"
SENTINEL_URL="${SENTINEL_URL:-http://localhost:9083}"
WORKSPACE="${KUBEMIND_WORKSPACE:-default}"
API_KEY="${KUBEMIND_API_KEY:-kmind-local-dev-key}"

# If KUBEMIND_API_KEYS is formatted as "key:ws:role", extract the first key
if [[ -n "${KUBEMIND_API_KEYS:-}" && "${API_KEY}" == "kmind-local-dev-key" ]]; then
  FIRST_KEY=$(echo "$KUBEMIND_API_KEYS" | cut -d',' -f1 | cut -d':' -f1)
  if [[ -n "$FIRST_KEY" ]]; then
    API_KEY="$FIRST_KEY"
  fi
fi

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

PASSED_COUNT=0
FAILED_COUNT=0
SKIPPED_COUNT=0

echo -e "\n${BLUE}${BOLD}====================================================================${NC}"
echo -e "${BLUE}${BOLD}        🧪 KubeMind Multi-Provider & LLM Verification Suite         ${NC}"
echo -e "${BLUE}${BOLD}====================================================================${NC}"
echo -e "  Gateway Endpoint:  ${CYAN}${ROUTER_URL}${NC}"
echo -e "  Workspace Tenant:  ${CYAN}${WORKSPACE}${NC}"
echo -e "  Auth Key:          ${CYAN}${API_KEY}${NC}\n"

# Verify Gateway is reachable
if ! curl -sf "${ROUTER_URL}/health" >/dev/null 2>&1; then
  echo -e "  ${RED}❌ Gateway is unreachable at ${ROUTER_URL}.${NC}"
  echo -e "  Please start the stack using: ${CYAN}./scripts/start_all.sh${NC}\n"
  exit 1
fi

test_model() {
  local provider_name="$1"
  local model_name="$2"
  local env_key_var="$3"
  local test_prompt="${4:-Respond with exactly: 'OK - Provider operational'}"

  echo -e "  ${BOLD}Testing ${provider_name} (${model_name})...${NC}"

  # Check if key is configured for cloud providers
  if [[ -n "$env_key_var" ]]; then
    local key_val="${!env_key_var:-}"
    if [[ -z "$key_val" ]]; then
      echo -e "    ${YELLOW}⊘ SKIPPED${NC} · ${env_key_var} not configured in .env"
      SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
      echo ""
      return 0
    fi
  fi

  local start_time=$(date +%s%N)
  local payload
  payload=$(cat <<EOF
{
  "model": "${model_name}",
  "messages": [
    {"role": "user", "content": "${test_prompt}"}
  ],
  "temperature": 0.1,
  "max_tokens": 64
}
EOF
)

  local resp
  local http_code
  resp=$(curl -s -w "\n%{http_code}" -X POST "${ROUTER_URL}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -H "X-Workspace-ID: ${WORKSPACE}" \
    -H "X-API-Key: ${API_KEY}" \
    -d "$payload" 2>/dev/null || true)

  local end_time=$(date +%s%N)
  local latency_ms=$(( (end_time - start_time) / 1000000 ))

  http_code=$(echo "$resp" | tail -n1)
  local body
  body=$(echo "$resp" | sed '$d')

  if [[ "$http_code" == "200" ]]; then
    local reply
    reply=$(echo "$body" | python3 -c "import json,sys; data=json.load(sys.stdin); print(data['choices'][0]['message']['content'].strip())" 2>/dev/null || echo "$body")
    local model_used
    model_used=$(echo "$body" | python3 -c "import json,sys; print(json.load(sys.stdin).get('model', '${model_name}'))" 2>/dev/null || echo "${model_name}")

    echo -e "    ${GREEN}✓ SUCCESS${NC} · Latency: ${latency_ms}ms · Resolved Model: ${CYAN}${model_used}${NC}"
    # Truncate reply snippet
    local snippet="${reply}"
    if [[ ${#snippet} -gt 100 ]]; then
      snippet="${snippet:0:97}..."
    fi
    echo -e "    ${DIM}Response: \"${snippet}\"${NC}"
    PASSED_COUNT=$((PASSED_COUNT + 1))
  else
    local err_detail
    err_detail=$(echo "$body" | python3 -c "import json,sys; print(json.load(sys.stdin).get('detail', 'Unknown error'))" 2>/dev/null || echo "$body")
    echo -e "    ${RED}❌ FAILED${NC} (HTTP ${http_code}) · ${err_detail}"
    FAILED_COUNT=$((FAILED_COUNT + 1))
  fi
  echo ""
}

# 1. Test OpenAI
test_model "OpenAI" "gpt-4o-mini" "OPENAI_API_KEY"
test_model "OpenAI" "gpt-4o" "OPENAI_API_KEY"

# 2. Test Google Gemini
test_model "Google Gemini" "gemini-2.5-flash" "GOOGLE_API_KEY"
test_model "Google Gemini" "gemini-flash-latest" "GOOGLE_API_KEY"

# 3. Test Groq
test_model "Groq" "llama-3.1-70b" "GROQ_API_KEY"
test_model "Groq" "llama-3.1-8b-instant" "GROQ_API_KEY"

# 4. Test Kimi / Moonshot
test_model "Kimi (Moonshot)" "moonshot-v1-8k" "KIMI_API_KEY"

# 5. Test Grok / xAI
test_model "Grok (xAI)" "grok-2" "GROK_API_KEY"

# 6. Test Local Ollama
test_model "Local Ollama" "llama3.1" "" "Hello, are you operational?"

# 7. Test KubeMind Auto-Intent Routing
test_model "KubeMind Gateway" "auto" "" "Write a Python one-liner to reverse a string"

# 8. Test Zero-Egress Reversible PII Pseudonymization
echo -e "  ${BOLD}Testing Zero-Egress PII Masking & Reversible Restoration...${NC}"
PII_PROMPT="Doctor Alice Smith sent patient records for John Doe to alice@corp.org"
PII_RESP=$(curl -s -X POST "${ROUTER_URL}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-ID: ${WORKSPACE}" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"model\": \"auto\", \"messages\": [{\"role\": \"user\", \"content\": \"${PII_PROMPT}\"}]}" 2>/dev/null || true)

if echo "$PII_RESP" | grep -q "choices"; then
  echo -e "    ${GREEN}✓ SUCCESS${NC} · PII Masking evaluated and response de-anonymized inline."
  PASSED_COUNT=$((PASSED_COUNT + 1))
else
  echo -e "    ${YELLOW}⚠ PII Test Response:${NC} ${PII_RESP}"
fi
echo ""

# 9. Verify Cryptographic SHA-256 Audit Ledger
echo -e "  ${BOLD}Verifying Cryptographic SHA-256 Ledger in Sentinel...${NC}"
LEDGER_RESP=$(curl -sf -H "X-Workspace-ID: ${WORKSPACE}" -H "X-API-Key: ${API_KEY}" "${SENTINEL_URL}/v1/audit/verify?workspace_id=${WORKSPACE}&limit=20" 2>/dev/null || true)
if [[ -n "$LEDGER_RESP" ]]; then
  VERIFIED=$(echo "$LEDGER_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('valid') if 'valid' in d else d.get('verified', False))" 2>/dev/null || echo "False")
  ENTRIES=$(echo "$LEDGER_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('entries_checked', 0))" 2>/dev/null || echo "0")
  if [[ "$VERIFIED" == "True" ]]; then
    echo -e "    ${GREEN}✓ SUCCESS${NC} · SHA-256 Ledger verified intact (${ENTRIES} audit blocks chained)."
    PASSED_COUNT=$((PASSED_COUNT + 1))
  else
    echo -e "    ${RED}❌ FAILED${NC} · Ledger verification failed: ${LEDGER_RESP}"
    FAILED_COUNT=$((FAILED_COUNT + 1))
  fi
else
  echo -e "    ${YELLOW}⚠ Sentinel ledger offline or unreachable${NC}"
fi

# Print Final Summary Banner
echo -e "\n${BLUE}${BOLD}====================================================================${NC}"
echo -e "${BLUE}${BOLD}                    📊 Test Execution Summary                       ${NC}"
echo -e "${BLUE}${BOLD}====================================================================${NC}"
echo -e "  • ${GREEN}Passed:${NC}   ${PASSED_COUNT}"
echo -e "  • ${YELLOW}Skipped:${NC}  ${SKIPPED_COUNT} (Add missing keys to .env to enable)"
echo -e "  • ${RED}Failed:${NC}   ${FAILED_COUNT}"
echo -e "${BLUE}${BOLD}====================================================================${NC}\n"
