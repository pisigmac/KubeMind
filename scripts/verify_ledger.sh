#!/usr/bin/env bash
# ==============================================================================
# KubeMind Cryptographic SHA-256 Audit Ledger Verification Utility
#
# Verifies the tamper-evident cryptographic hash-chain across Sentinel audit blocks.
#
# Usage:
#   ./scripts/verify_ledger.sh [WORKSPACE_ID] [LIMIT]
# ==============================================================================

set -euo pipefail

SENTINEL_URL="${SENTINEL_URL:-http://localhost:9083}"
WORKSPACE="${1:-default}"
LIMIT="${2:-100}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "\n${CYAN}${BOLD}====================================================================${NC}"
echo -e "${CYAN}${BOLD}    🛡️ Cryptographic SHA-256 Audit Ledger Verification (${WORKSPACE})   ${NC}"
echo -e "${CYAN}${BOLD}====================================================================${NC}\n"

RESP=$(curl -sf "${SENTINEL_URL}/v1/audit/verify?workspace_id=${WORKSPACE}&limit=${LIMIT}" 2>/dev/null || true)

if [[ -z "$RESP" ]]; then
  echo -e "  ${RED}❌ Failed to connect to Sentinel at ${SENTINEL_URL}${NC}\n"
  exit 1
fi

echo -e "  Raw Ledger Response: ${CYAN}${RESP}${NC}\n"

python3 - <<EOF
import json, sys

data = json.loads('''$RESP''')
verified = data.get("verified", False)
entries_checked = data.get("entries_checked", 0)
head_hash = data.get("head_hash", "None")

if verified:
    print(f"\033[0;32m\033[1m✓ AUDIT LEDGER INTEGRITY VERIFIED (100% INTACT)\033[0m")
    print(f"  • Workspace:       ${WORKSPACE}")
    print(f"  • Blocks Checked:  {entries_checked}")
    print(f"  • Head SHA-256:    {head_hash}")
    print(f"  • Hash-Chain:      Valid and tamper-evident.\n")
    sys.exit(0)
else:
    print(f"\033[0;31m\033[1m❌ AUDIT LEDGER TAMPERING DETECTED OR CHAIN BROKEN\033[0m")
    print(f"  • Details: {data}\n")
    sys.exit(1)
EOF
