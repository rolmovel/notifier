#!/usr/bin/env bash

# ==============================================================================
# Start WhatsApp Appointment Notifier Services
# ==============================================================================

set -e

# Get scripts directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source shared helpers
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

# Pre-requisite validations
verify_env_file
verify_docker

log_info "Starting WhatsApp Appointment Notifier Docker Stack..."

# Load env variables for reference in output messages
load_env

# Start containers
# Run docker compose from the docker/ directory so relative paths in docker-compose.yml resolve correctly
cd "${PROJECT_ROOT}/docker"
docker compose up -d

log_success "All docker services have been started successfully!"
echo -e "--------------------------------------------------------"
log_info "Service URLs under current configurations:"
echo -e "  - n8n Orchestrator:  ${N8N_PROTOCOL:-http}://${N8N_HOST:-localhost}:${N8N_PORT:-5678}/"
echo -e "  - Evolution API:     http://localhost:${EVOLUTION_API_PORT:-8080}/"
echo -e "--------------------------------------------------------"
log_info "To scan the WhatsApp connection QR code, run: \n  ./scripts/setup-evolution.sh"
echo -e "--------------------------------------------------------"
