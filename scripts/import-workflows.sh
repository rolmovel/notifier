#!/usr/bin/env bash

# ==============================================================================
# Import n8n Workflow JSON Files into n8n Container Database
# ==============================================================================

set -e

# Get scripts directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source shared helpers
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

verify_docker

log_info "Synchronizing and Importing n8n Workflows..."

# Ensure n8n container is actually running
if [ "$(docker inspect -f '{{.State.Running}}' notifier-n8n 2>/dev/null)" != "true" ]; then
  log_error "The 'notifier-n8n' container is not running!"
  log_error "Please start your services first by running: ./scripts/start.sh"
  exit 1
fi

log_info "Found running 'notifier-n8n' container. Importing workflows from inside mounting point..."

# 1. Import Send Appointments Workflow
log_info "Importing 'Send Appointment Notifications' workflow..."
docker exec notifier-n8n n8n import:workflow --input /opt/notifier/workflows/send-appointments.json

# 2. Import Receive Patient Reply Workflow
log_info "Importing 'Receive Patient Reply & Bot Response' workflow..."
docker exec notifier-n8n n8n import:workflow --input /opt/notifier/workflows/receive-reply.json

# 3. Import Health Check Workflow (if it exists inside folder)
if [ -f "${PROJECT_ROOT}/docker/n8n/workflows/health-check.json" ]; then
  log_info "Importing 'System Health Check' workflow..."
  docker exec notifier-n8n n8n import:workflow --input /opt/notifier/workflows/health-check.json
fi

# 4. Activate all imported workflows
log_info "Activating all imported workflows..."

# List all workflow IDs from the n8n database and activate each one
workflow_ids=$(docker exec notifier-n8n n8n list:workflow 2>/dev/null | grep -oE '^[[:space:]]*[0-9]+' | tr -d ' ' || true)

if [ -n "${workflow_ids}" ]; then
  echo "${workflow_ids}" | while read -r wid; do
    log_info "Activating workflow ID: ${wid}..."
    docker exec notifier-n8n n8n update:workflow --id "${wid}" --active=true 2>/dev/null || \
      log_warn "Could not activate workflow ID ${wid} (may require credential configuration in n8n UI first)."
  done
else
  log_warn "Could not retrieve workflow IDs automatically. Please activate workflows manually in the n8n UI."
fi

log_success "All workflows have been imported and activated!"
echo -e "--------------------------------------------------------"
log_info "Workflows are now active and webhook endpoints are registered."
log_info "If any workflow failed to activate, visit the n8n UI to configure credentials and toggle it on."
echo -e "--------------------------------------------------------"
