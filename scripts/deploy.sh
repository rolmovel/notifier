#!/usr/bin/env bash

# ==============================================================================
# Production Deployment Automation Script
# ==============================================================================

set -e

# Get scripts directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source shared helpers
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

verify_docker

log_info "Initializing Release Deployment Process..."

# Ensure target directories are ready and permissions are sound
log_info "Verifying permissions..."
chmod +x "${PROJECT_ROOT}/scripts"/*.sh

# Interactive/automatic .env provision check
if [ ! -f "${PROJECT_ROOT}/docker/.env" ]; then
  log_warn "A local 'docker/.env' configuration is missing!"
  log_info "Creating 'docker/.env' from template..."
  cp "${PROJECT_ROOT}/docker/.env.example" "${PROJECT_ROOT}/docker/.env"
  log_warn "--------------------------------------------------------"
  log_warn "A default configuration has been set up at docker/.env"
  log_warn "PLEASE MODIFY the secret keys inside of docker/.env before running start.sh!"
  log_warn "--------------------------------------------------------"
else
  log_success "Found active 'docker/.env' file. Ready to start services."
fi

# Load variables
load_env

# Build and start services using our wrapper
log_info "Running system service build & launch sequence..."
"${PROJECT_ROOT}/scripts/start.sh"

# Perform initial configuration
log_info "Verifying container orchestration state..."
sleep 5 # short sleep for containers to bind initial ports

if [ "$(docker inspect -f '{{.State.Running}}' notifier-n8n 2>/dev/null)" = "true" ]; then
  log_success "n8n service is healthy and reachable."
  log_info "Syncing workflows..."
  "${PROJECT_ROOT}/scripts/import-workflows.sh" || log_warn "Initial import failed - n8n might need additional startup seconds."
else
  log_warn "n8n is taking longer to start. You may need to manually run import-workflows.sh later."
fi

log_success "Deployment Sequence finished successfully!"
echo -e "--------------------------------------------------------"
log_info "Verify everything works by checking: \n  docker compose ps"
echo -e "--------------------------------------------------------"
