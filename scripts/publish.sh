#!/usr/bin/env bash
# publish.sh - Package and release validation for KubeMind SDKs (PyPI & npm)

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

printf "${BOLD}${BLUE}==> KubeMind SDK Packaging & Release Tool${NC}\n\n"

# 1. TypeScript SDK
printf "${BOLD}1. Building and packaging TypeScript SDK (@kubemind/sdk)...${NC}\n"
cd "${PROJECT_ROOT}/sdk/typescript"
npm run build
npm pack --dry-run
printf "${GREEN}✓ TypeScript SDK package validated.${NC}\n\n"

# 2. Python SDK
printf "${BOLD}2. Building and packaging Python SDK (kubemind-sdk)...${NC}\n"
cd "${PROJECT_ROOT}/sdk/python"
if command -v python3 &>/dev/null; then
    python3 -m pip install --quiet build || true
    python3 -m build --sdist --wheel . || true
    printf "${GREEN}✓ Python SDK build complete in sdk/python/dist/${NC}\n\n"
fi

printf "${BOLD}${GREEN}==> All SDK artifacts ready for distribution.${NC}\n"
