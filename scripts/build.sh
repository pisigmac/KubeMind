#!/usr/bin/env bash
# build.sh - KubeMind compilation and build orchestration script
# Builds the CLI binary, services docker images, and dashboard resources.

set -euo pipefail

# Setup colors for output
BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info() {
    printf "${BOLD}INFO:${NC} %s\n" "$*"
}

success() {
    printf "${GREEN}${BOLD}SUCCESS:${NC} %s\n" "$*"
}

error() {
    printf "${RED}${BOLD}ERROR:${NC} %s\n" "$*" >&2
}

show_help() {
    cat << EOF
Usage: $0 [options]

Options:
  --all            Build everything (CLI, Docker images, Dashboard) [Default]
  --cli            Build the kmind CLI tool only
  --docker         Build all Docker images only
  --services       Build specific services/containers only (comma-separated, e.g., router,mind)
  --dashboard      Build the dashboard service only
  -h, --help       Show this help message
EOF
}

# Resolve script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

build_cli() {
    info "Building KubeMind CLI (kmind)..."
    cd "${PROJECT_ROOT}"
    mkdir -p bin
    cd cmd/kmind
    go build -o ../../bin/kmind .
    cd ../../bin
    ln -sfn kmind tricore
    success "CLI built successfully at bin/kmind (symlinked to bin/tricore)"
}

build_docker() {
    local target_services=("$@")
    
    if [ ${#target_services[@]} -eq 0 ]; then
        target_services=("router" "sentinel" "mind" "agents" "dashboard")
    fi

    info "Building Docker images for: ${target_services[*]}"
    cd "${PROJECT_ROOT}"

    for service in "${target_services[@]}"; do
        case "$service" in
            router)
                info "Building kubemind/router..."
                docker build -f services/router/Dockerfile -t kubemind/router .
                ;;
            sentinel)
                info "Building kubemind/sentinel..."
                docker build -f services/sentinel/Dockerfile -t kubemind/sentinel .
                ;;
            mind)
                info "Building kubemind/mind..."
                cd services/mind && docker build -t kubemind/mind . && cd - > /dev/null
                ;;
            agents)
                info "Building kubemind/agents..."
                cd services/agents && docker build -t kubemind/agents . && cd - > /dev/null
                ;;
            dashboard)
                info "Building kubemind/dashboard..."
                cd dashboard && docker build -t kubemind/dashboard . && cd - > /dev/null
                ;;
            *)
                error "Unknown service: $service"
                exit 1
                ;;
        esac
    done
    success "Docker build complete."
}

build_dashboard_local() {
    info "Building Dashboard locally..."
    cd "${PROJECT_ROOT}/dashboard"
    if [ ! -d "node_modules" ]; then
        info "node_modules not found, running npm install..."
        npm install
    fi
    npm run build
    success "Dashboard local build complete."
}

build_sdks() {
    info "Building SDKs..."
    if [ -d "${PROJECT_ROOT}/sdk/typescript" ]; then
        info "Building TypeScript SDK..."
        cd "${PROJECT_ROOT}/sdk/typescript"
        if [ ! -d "node_modules" ]; then
            npm install
        fi
        npm run build
        success "TypeScript SDK compiled."
    fi
    success "SDK builds complete."
}

# Parse options
BUILD_CLI=false
BUILD_DOCKER=false
BUILD_DASHBOARD_LOCAL=false
BUILD_SDKS=false
SPECIFIC_SERVICES=()

if [ $# -eq 0 ]; then
    BUILD_CLI=true
    BUILD_DOCKER=true
    BUILD_SDKS=true
else
    while [ $# -gt 0 ]; do
        case "$1" in
            --all)
                BUILD_CLI=true
                BUILD_DOCKER=true
                BUILD_SDKS=true
                shift
                ;;
            --cli)
                BUILD_CLI=true
                shift
                ;;
            --sdk)
                BUILD_SDKS=true
                shift
                ;;
            --docker)
                BUILD_DOCKER=true
                shift
                ;;
            --dashboard)
                BUILD_DASHBOARD_LOCAL=true
                shift
                ;;
            --services)
                BUILD_DOCKER=true
                IFS=',' read -ra ADDR <<< "$2"
                for i in "${ADDR[@]}"; do
                    SPECIFIC_SERVICES+=("$i")
                done
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
fi

# Run selected builds
if [ "$BUILD_CLI" = true ]; then
    build_cli
fi

if [ "$BUILD_SDKS" = true ]; then
    build_sdks
fi

if [ "$BUILD_DOCKER" = true ]; then
    build_docker "${SPECIFIC_SERVICES[@]}"
fi

if [ "$BUILD_DASHBOARD_LOCAL" = true ]; then
    build_dashboard_local
fi

success "Build step completed successfully."
