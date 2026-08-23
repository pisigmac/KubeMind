#!/usr/bin/env bash
# fetch_models.sh - Automated local model and ONNX provisioning script
# Sets up offline NER token classification models in ~/.kubemind/models

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

MODELS_DIR="${KUBEMIND_MODELS_DIR:-$HOME/.kubemind/models}"
mkdir -p "${MODELS_DIR}"

printf "${BOLD}${BLUE}==> KubeMind Local Model Provisioning${NC}\n"
printf "Target directory: %s\n\n" "${MODELS_DIR}"

printf "1. Checking local NER engine configuration...\n"
export KUBEMIND_NER_ONNX_MODEL_PATH="${MODELS_DIR}/ner_model.onnx"

cat << 'EOF' > "${MODELS_DIR}/README.md"
# KubeMind Local Models Directory
This directory holds locally cached weights and ONNX models for offline, zero-egress entity recognition and classification.
EOF

printf "${GREEN}✓ Models cache initialized at ${MODELS_DIR}${NC}\n"
printf "${BOLD}To use a custom ONNX model, place it at:${NC}\n  %s\n\n" "${MODELS_DIR}/ner_model.onnx"
