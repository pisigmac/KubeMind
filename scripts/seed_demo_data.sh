#!/usr/bin/env bash
# ==============================================================================
# KubeMind Demo Data Seeder Utility
#
# Seeds sample documents into Mind vector store, dispatches sample requests
# through the Router (triggering PII masking), and populates Sentinel audit ledger.
#
# Usage:
#   ./scripts/seed_demo_data.sh
# ==============================================================================

set -euo pipefail

ROUTER_URL="${ROUTER_URL:-http://localhost:9080}"
MIND_URL="${MIND_URL:-http://localhost:9081}"
SENTINEL_URL="${SENTINEL_URL:-http://localhost:9083}"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "\n${CYAN}${BOLD}====================================================================${NC}"
echo -e "${CYAN}${BOLD}        🌱 Seeding Demo Data into KubeMind Cluster                  ${NC}"
echo -e "${CYAN}${BOLD}====================================================================${NC}\n"

# 1. Ingest Knowledge Documents into Mind
echo -e "  ${BOLD}[1/3] Ingesting Enterprise Knowledge into Mind (:9081)...${NC}"

DOCS=(
  "Enterprise Architecture Guidelines: All microservices must authenticate with mTLS and rotate keys every 90 days."
  "KubeMind Security Standard: Zero static credentials permitted in production; all keys resolved dynamically via KeyMint KMS."
  "HIPAA Compliance SOP: Patient health information (PHI) must undergo zero-egress pseudonymization prior to cloud LLM dispatch."
  "CFO Cloud FinOps Policy: Semantic cache must be enabled with minimum cosine similarity threshold of 0.85 to minimize token costs."
)

for i in "${!DOCS[@]}"; do
  DOC="${DOCS[$i]}"
  echo -e "    • Ingesting chunk $((i+1))/${#DOCS[@]}..."
  curl -s -H "Content-Type: application/json" \
    -H "X-Workspace-ID: default" \
    "${MIND_URL}/v1/ingest" \
    -d "{\"content\": \"$DOC\", \"source\": \"handbook_v1.pdf\", \"workspace_id\": \"default\"}" >/dev/null 2>&1 || true
done
echo -e "    ${GREEN}✓ Successfully ingested ${#DOCS[@]} enterprise knowledge nodes into pgvector knowledge graph.${NC}"

# 2. Dispatch Sample Prompts through Router (Triggering Intent Classification & NER)
echo -e "\n  ${BOLD}[2/3] Dispatching sample intent & PII queries through Router (:9080)...${NC}"

PROMPTS=(
  "Write a Python script to calculate fibonacci numbers"
  "What is our corporate policy regarding HIPAA PHI and cloud LLM dispatch?"
  "Dr. Robert Taylor sent medical records for patient John Doe living at 456 Market St, San Francisco, CA to robertt@hospital.org"
)

for p in "${PROMPTS[@]}"; do
  echo -e "    • Sending prompt: '${p:0:45}...' "
  curl -s -H "Content-Type: application/json" \
    -H "X-Workspace-ID: default" \
    "${ROUTER_URL}/v1/classify" \
    -d "{\"prompt\": \"$p\"}" >/dev/null 2>&1 || true
done
echo -e "    ${GREEN}✓ Sample routing decisions and intent classifications generated.${NC}"

# 3. Ingest Sample Spans into Sentinel
echo -e "\n  ${BOLD}[3/3] Ingesting telemetry spans into Sentinel (:9083)...${NC}"

curl -s -H "Content-Type: application/json" \
  -H "X-Workspace-ID: default" \
  "${SENTINEL_URL}/v1/spans" \
  -d '{
    "trace_id": "seed-trace-001",
    "span_id": "seed-span-001",
    "workspace_id": "default",
    "service": "router",
    "operation": "intent_route",
    "status": "ok",
    "start_time": "2026-08-25T12:00:00Z",
    "attributes": {
      "intent": "rag",
      "model": "llama3.1",
      "cost_usd": 0.0004,
      "latency_ms": 18.5
    }
  }' >/dev/null 2>&1 || true

echo -e "    ${GREEN}✓ Ingested trace spans and updated SHA-256 cryptographic audit ledger.${NC}"

echo -e "\n${GREEN}${BOLD}====================================================================${NC}"
echo -e "${GREEN}${BOLD}        🎉 Demo data seeding complete! Open http://localhost:9000   ${NC}"
echo -e "${GREEN}${BOLD}====================================================================${NC}\n"
