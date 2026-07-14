#!/usr/bin/env bash

# ==============================================================================
# Setup Evolution API Instance and Webhooks
# ==============================================================================

set -e

# Get scripts directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source shared helpers
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

verify_env_file
load_env
verify_dependency curl

log_info "Initializing Evolution API WhatsApp Gateway..."

# 1. Create instance in Evolution API
log_info "Creating WhatsApp Instance: ${EVOLUTION_INSTANCE_NAME}..."

# We call the local API. In docker network, it connects to 'localhost' or 'url' as configured.
# We'll use the external URL (or localhost if direct) to set up
API_BASE_URL="http://localhost:${EVOLUTION_API_PORT:-8080}"

response=$(curl -s -X POST "${API_BASE_URL}/instance/create" \
  -H "Content-Type: application/json" \
  -H "apikey: ${EVOLUTION_API_KEY}" \
  -d "{\"instanceName\":\"${EVOLUTION_INSTANCE_NAME}\",\"qrcode\":true,\"integration\":\"WHATSAPP-BAILEYS\"}")

# Parse instance status or qrcode
if echo "$response" | grep -q 'created\|instanceName'; then
  log_success "Instance '${EVOLUTION_INSTANCE_NAME}' created or retrieved successfully."
else
  log_error "Failed to create instance. API Response: $response"
  exit 1
fi

# 2. Extract QR Code if available
qrcode_base64=$(echo "$response" | grep -o '"base64":"[^"]*' | head -1 | cut -d'"' -f4 || true)

if [ -n "$qrcode_base64" ]; then
  log_success "WhatsApp Connection QR Code retrieved!"
  log_info "Please copy-paste the base64 or render it in your browser to scan."
  log_info "You can also view the QR code anytime on the Evolution API panel or UI."
  echo -e "--------------------------------------------------------"
  echo "$qrcode_base64" | head -c 100
  echo -e "... [ truncated base64 code ] ..."
  echo -e "--------------------------------------------------------"
else
  log_warn "Instance could be already connected or QR code was not returned in the payload."
fi

# 3. Configure webhook URL pointing to n8n webhook-path
# Webhook destination is n8n container internal port on the Docker bridge network
# n8n container name: notifier-n8n (port 5678)
# Webhook: http://n8n:5678/webhook/receive-reply
WEBHOOK_DEST_URL="http://notifier-n8n:5678/webhook/receive-reply"

log_info "Setting up webhook on Evolution API instance targeting: ${WEBHOOK_DEST_URL}..."

webhook_response=$(curl -s -X POST "${API_BASE_URL}/webhook/set/${EVOLUTION_INSTANCE_NAME}" \
  -H "Content-Type: application/json" \
  -H "apikey: ${EVOLUTION_API_KEY}" \
  -d "{\"webhook\":{\"enabled\":true,\"url\":\"${WEBHOOK_DEST_URL}\",\"events\":[\"MESSAGES_UPSERT\",\"CONNECTION_UPDATE\"]}}")

if echo "$webhook_response" | grep -q '"enabled":true'; then
  log_success "Webhook configured successfully."
else
  log_warn "Could not confirm webhook status in response: $webhook_response"
fi

log_success "Evolution API Setup Completed!"
echo -e "--------------------------------------------------------"
log_info "Next Steps:"
echo -e "  1. If you saw a QR code, scan it using WhatsApp linked devices."
echo -e "  2. Go ahead and start sending reminders using: \n     ./scripts/import-workflows.sh"
echo -e "--------------------------------------------------------"
