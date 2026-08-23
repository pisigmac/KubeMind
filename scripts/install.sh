#!/usr/bin/env bash
# install.sh - KubeMind environment initialization and installation helper
# Handles dependencies check, environment variables setup, and building components.

set -euo pipefail

# Setup colors for output
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info() {
    printf "${BOLD}INFO:${NC} %s\n" "$*"
}

success() {
    printf "${GREEN}${BOLD}SUCCESS:${NC} %s\n" "$*"
}

warn() {
    printf "${YELLOW}${BOLD}WARNING:${NC} %s\n" "$*"
}

error() {
    printf "${RED}${BOLD}ERROR:${NC} %s\n" "$*" >&2
}

# Resolve script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

check_cmd() {
    local cmd="$1"
    local required="$2"
    if command -v "$cmd" >/dev/null 2>&1; then
        info "Found dependency: $cmd"
        return 0
    else
        if [ "$required" = "true" ]; then
            error "Required dependency missing: $cmd. Please install it first."
            return 1
        else
            warn "Optional dependency missing: $cmd. Some components/development tasks may not work."
            return 0
        fi
    fi
}

info "Initializing KubeMind installation..."

# 1. Dependency checks
HAS_ERRORS=0
check_cmd "docker" "true" || HAS_ERRORS=1
check_cmd "go" "false"
check_cmd "python3" "false"
check_cmd "npm" "false"
check_cmd "helm" "false"

# Check Docker Compose (either v1 or v2 syntax)
if docker compose version >/dev/null 2>&1; then
    info "Found dependency: docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    info "Found dependency: docker-compose"
else
    error "Docker Compose (v2 plugin or standalone docker-compose v1) is required."
    HAS_ERRORS=1
fi

if [ $HAS_ERRORS -ne 0 ]; then
    error "Cannot proceed. Please install the missing required dependencies and re-run this script."
    exit 1
fi

# 2. Config setup
cd "${PROJECT_ROOT}"
if [ ! -f ".env" ]; then
    info "Copying .env.example to .env..."
    cp .env.example .env
    success "Created .env configuration file."
else
    info ".env file already exists. Skipping copy."
fi

# 3. Setup Python virtual environment for local dev/testing
if command -v python3 >/dev/null 2>&1; then
    if [ ! -d ".venv" ]; then
        info "Creating python virtual environment (.venv)..."
        python3 -m venv .venv
        success "Python virtual environment created."
    fi
    
    info "Installing python dev-dependencies into virtual environment..."
    # Execute within subshell or explicitly call .venv/bin/pip
    if [ -f "requirements-dev.txt" ]; then
        .venv/bin/pip install --upgrade pip
        .venv/bin/pip install -r requirements-dev.txt
        success "Python dependencies installed successfully."
    fi
fi

# 4. Prompt to build
info "Do you want to run build.sh now to build KubeMind components? (Y/n)"
# Non-interactive fallback or default to yes
read -r -t 10 response || response="yes"
if [[ "$response" =~ ^[Nn] ]]; then
    info "Build skipped. You can manually build by running ./scripts/build.sh or make build."
else
    info "Triggering build.sh..."
    "${SCRIPT_DIR}/build.sh"
fi

# 5. Path helper info
success "KubeMind installation setup complete!"
echo ""
echo "Next steps:"
echo "1. Run the stack:        make up"
echo "2. Check status:          make status"
echo "3. Run the partner demo:  make demo"
echo ""
echo "CLI access:"
echo "The CLI binary is built at ${PROJECT_ROOT}/bin/kmind"
echo "You can add it to your PATH or run it directly."
echo "E.g., export PATH=\"\$PATH:${PROJECT_ROOT}/bin\""
echo ""
