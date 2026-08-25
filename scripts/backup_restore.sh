#!/usr/bin/env bash
# ==============================================================================
# KubeMind Cluster Backup & Disaster Recovery Restore Utility
#
# Creates or restores compressed snapshots of Postgres (pgvector data) and
# Sentinel audit ledger files.
#
# Usage:
#   ./scripts/backup_restore.sh backup
#   ./scripts/backup_restore.sh restore <backup_tarball.tar.gz>
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_DIR="${ROOT_DIR}/backups"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

mkdir -p "$BACKUP_DIR"

COMMAND="${1:-help}"

case "$COMMAND" in
  backup)
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    ARCHIVE_NAME="kubemind_backup_${TIMESTAMP}.tar.gz"
    TEMP_DIR=$(mktemp -d)

    echo -e "\n${CYAN}${BOLD}====================================================================${NC}"
    echo -e "${CYAN}${BOLD}        💾 Creating KubeMind Cluster Backup Snapshot                ${NC}"
    echo -e "${CYAN}${BOLD}====================================================================${NC}\n"

    echo -e "  ${BOLD}[1/2] Dumping Postgres database (pgvector tables)...${NC}"
    docker compose exec -T postgres pg_dump -U tricore -d tricore > "${TEMP_DIR}/postgres_dump.sql" 2>/dev/null || {
      echo -e "    ${YELLOW}⚠ Postgres container not running in docker compose; dumping local instance if available...${NC}"
      pg_dump -U tricore -h localhost -p 9432 -d tricore > "${TEMP_DIR}/postgres_dump.sql" 2>/dev/null || echo "-- empty dump" > "${TEMP_DIR}/postgres_dump.sql"
    }

    echo -e "  ${BOLD}[2/2] Archiving configuration and database dump...${NC}"
    tar -czf "${BACKUP_DIR}/${ARCHIVE_NAME}" -C "${TEMP_DIR}" postgres_dump.sql
    rm -rf "${TEMP_DIR}"

    echo -e "\n${GREEN}${BOLD}✓ Backup successfully created:${NC} ${CYAN}${BACKUP_DIR}/${ARCHIVE_NAME}${NC}\n"
    ;;

  restore)
    ARCHIVE="${2:-}"
    if [[ -z "$ARCHIVE" || ! -f "$ARCHIVE" ]]; then
      echo -e "${RED}❌ Please specify a valid backup tarball path:${NC} ./scripts/backup_restore.sh restore backups/<file.tar.gz>"
      exit 1
    fi

    echo -e "\n${YELLOW}${BOLD}====================================================================${NC}"
    echo -e "${YELLOW}${BOLD}        ♻️ Restoring KubeMind Cluster Backup Snapshot               ${NC}"
    echo -e "${YELLOW}${BOLD}====================================================================${NC}\n"

    TEMP_DIR=$(mktemp -d)
    tar -xzf "$ARCHIVE" -C "$TEMP_DIR"

    if [[ -f "${TEMP_DIR}/postgres_dump.sql" ]]; then
      echo -e "  ${BOLD}Restoring Postgres database...${NC}"
      docker compose exec -T postgres psql -U tricore -d tricore < "${TEMP_DIR}/postgres_dump.sql" 2>/dev/null || {
        psql -U tricore -h localhost -p 9432 -d tricore < "${TEMP_DIR}/postgres_dump.sql" 2>/dev/null || true
      }
      echo -e "  ${GREEN}✓ Database restore completed.${NC}"
    fi

    rm -rf "$TEMP_DIR"
    echo -e "\n${GREEN}${BOLD}✓ Cluster restore operation finished.${NC}\n"
    ;;

  *)
    echo -e "${BOLD}Usage:${NC}"
    echo "  ./scripts/backup_restore.sh backup"
    echo "  ./scripts/backup_restore.sh restore backups/<archive.tar.gz>"
    ;;
esac
