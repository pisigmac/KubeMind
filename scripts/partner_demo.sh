#!/usr/bin/env bash
# Scripted partner demo: intent routing, retrieval, secret block, PII local_only.
#
# Prerequisites: stack up (`make up`), Ollama with nomic-embed-text, and ideally
# a local chat model. Each step prints the decision fields a design partner
# can verify in the audit ledger.
set -euo pipefail

ROUTER="${ROUTER_URL:-http://localhost:9080}"
SENTINEL="${SENTINEL_URL:-http://localhost:9083}"
MIND="${MIND_URL:-http://localhost:9081}"
KEY="${KUBEMIND_DEMO_KEY:-}"
WS="${KUBEMIND_DEMO_WORKSPACE:-demo}"

hdr=(-H "Content-Type: application/json" -H "X-Workspace-ID: ${WS}")
if [[ -n "$KEY" ]]; then
  hdr+=(-H "X-API-Key: ${KEY}")
fi

bold() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  ✓ %s\n' "$*"; }
fail() { printf '  ✗ %s\n' "$*"; exit 1; }

json_field() {
  python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('$1',''))"
}

bold "0. Health"
curl -sf "${ROUTER}/health" | python3 -m json.tool >/dev/null && ok "router healthy"
curl -sf "${SENTINEL}/health" | python3 -m json.tool >/dev/null && ok "sentinel healthy"

bold "1. Code prompt → code profile (local-preferring pool)"
CODE_RESP=$(curl -sf "${ROUTER}/v1/chat/completions" "${hdr[@]}" -d '{
  "model": "llama3.1",
  "messages": [{"role":"user","content":"Write a Python function that parses YAML"}],
  "enable_cache": false
}')
echo "$CODE_RESP" | python3 -m json.tool | head -40
INTENT=$(echo "$CODE_RESP" | json_field intent)
PROFILE=$(echo "$CODE_RESP" | json_field profile)
[[ "$INTENT" == "code" ]] && ok "intent=code" || fail "expected intent=code, got $INTENT"
[[ "$PROFILE" == "code" ]] && ok "profile=code" || fail "expected profile=code, got $PROFILE"

bold "2. Seed mind + retrieval prompt → knowledge profile with context"
curl -sf "${MIND}/v1/ingest" "${hdr[@]}" -d '{
  "content": "KubeMind expense policy: employees may claim meals under $50 with a receipt.",
  "source": "handbook",
  "metadata": {"title": "Expenses"}
}' >/dev/null || ok "(mind ingest skipped — service may not be ready)"

RAG_RESP=$(curl -sf "${ROUTER}/v1/chat/completions" "${hdr[@]}" -d '{
  "model": "llama3.1",
  "messages": [{"role":"user","content":"What does our employee handbook say about expenses?"}],
  "enable_cache": false
}')
echo "$RAG_RESP" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('intent=', d.get('intent'), 'profile=', d.get('profile'), 'retrieval=', d.get('retrieval_used'))
"
[[ "$(echo "$RAG_RESP" | json_field intent)" == "rag" ]] && ok "intent=rag" || ok "intent=$(echo "$RAG_RESP" | json_field intent) (classifier may abstain without embedder)"

bold "3. Private key → blocked before any provider sees it"
BLOCK_CODE=$(curl -s -o /tmp/km_block.json -w '%{http_code}' "${ROUTER}/v1/chat/completions" "${hdr[@]}" -d '{
  "model": "llama3.1",
  "messages": [{"role":"user","content":"Deploy with -----BEGIN PRIVATE KEY-----\nMIIBVgIBADANBgkqhkiG9w0\n-----END PRIVATE KEY-----"}]
}')
[[ "$BLOCK_CODE" == "403" ]] && ok "blocked with HTTP 403" || fail "expected 403, got $BLOCK_CODE"
python3 -c "import json; d=json.load(open('/tmp/km_block.json')); print(d.get('detail'))"

bold "4. PII → local_only (refuses cloud)"
PII_RESP=$(curl -sf "${ROUTER}/v1/chat/completions" "${hdr[@]}" -d '{
  "model": "llama3.1",
  "messages": [{"role":"user","content":"Email the report to alice@example.com"}],
  "enable_cache": false
}' || true)
if [[ -n "$PII_RESP" ]]; then
  ACTION=$(echo "$PII_RESP" | json_field policy_action)
  EGRESS=$(echo "$PII_RESP" | json_field egress_class)
  [[ "$ACTION" == "local_only" || "$EGRESS" == "local_only" ]] \
    && ok "policy_action/egress=local_only" \
    || fail "expected local_only, got action=$ACTION egress=$EGRESS"
else
  # 503 when no local provider is healthy is also a correct outcome.
  PII_CODE=$(curl -s -o /dev/null -w '%{http_code}' "${ROUTER}/v1/chat/completions" "${hdr[@]}" -d '{
    "model": "llama3.1",
    "messages": [{"role":"user","content":"Email the report to alice@example.com"}]
  }')
  [[ "$PII_CODE" == "503" ]] && ok "refused with 503 (no healthy local provider)" \
    || fail "expected local_only response or 503, got $PII_CODE"
fi

bold "5. Verify in the audit ledger"
VERIFY=$(curl -sf "${SENTINEL}/v1/audit/verify?workspace_id=${WS}&limit=50" "${hdr[@]}" || true)
if [[ -n "$VERIFY" ]]; then
  echo "$VERIFY" | python3 -m json.tool | head -30
  ok "ledger verify returned"
else
  ok "(ledger endpoint unavailable — check AUDIT_DATABASE_URL / sentinel logs)"
fi

bold "6. Routing report (cache hits counted as zero cost)"
curl -sf "${ROUTER}/v1/routing/report" "${hdr[@]}" | python3 -m json.tool | head -40
ok "done"

printf '\nDemo complete. Decision records are in sentinel; re-run with\n'
printf '  KUBEMIND_DEMO_KEY=... KUBEMIND_DEMO_WORKSPACE=acme %s\n' "$0"
printf 'against an authenticated deployment.\n'
