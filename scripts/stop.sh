#!/usr/bin/env bash

# ==============================================================================
# Stop WhatsApp Appointment Notifier Services
# ==============================================================================

set -e

# Get scripts directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source shared helpers
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

verify_docker

log_info "Stopping WhatsApp Appointment Notifier Docker Stack..."

# Stop containers
cd "${PROJECT_ROOT}/docker"
docker compose down

log_success "All docker services have been stopped."
