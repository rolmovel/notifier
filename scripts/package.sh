#!/usr/bin/env bash

# ==============================================================================
# Package WhatsApp Appointment Notifier Stack into a self-contained Tarball
# ==============================================================================

set -e

# Get scripts directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source shared helpers
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

log_info "Packaging WhatsApp Appointment Notifier Release..."

VERSION="1.0.0"
DIST_DIR="${PROJECT_ROOT}/dist"
TEMP_BUILD_DIR="${DIST_DIR}/notifier-${VERSION}"

# Clean of existing dist outputs
rm -rf "$DIST_DIR"
mkdir -p "$TEMP_BUILD_DIR"

log_info "Assembling deployment package layout..."

# Replicate clean directory structure in temp layout
mkdir -p "${TEMP_BUILD_DIR}/docker/n8n/workflows"
mkdir -p "${TEMP_BUILD_DIR}/docker/evolution-api"
mkdir -p "${TEMP_BUILD_DIR}/docker/postgres/init"
mkdir -p "${TEMP_BUILD_DIR}/scripts/lib"
mkdir -p "${TEMP_BUILD_DIR}/config/notification-templates"
mkdir -p "${TEMP_BUILD_DIR}/docs"

# Copy compose and env configs
cp "${PROJECT_ROOT}/docker/docker-compose.yml" "${TEMP_BUILD_DIR}/docker/"
cp "${PROJECT_ROOT}/docker/.env.example" "${TEMP_BUILD_DIR}/docker/"
cp "${PROJECT_ROOT}/docker/evolution-api/evolution.env" "${TEMP_BUILD_DIR}/docker/evolution-api/"
cp "${PROJECT_ROOT}/docker/postgres/init"/*.sql "${TEMP_BUILD_DIR}/docker/postgres/init/"
cp "${PROJECT_ROOT}/docker/n8n/Dockerfile" "${TEMP_BUILD_DIR}/docker/n8n/"
cp "${PROJECT_ROOT}/docker/n8n/workflows"/*.json "${TEMP_BUILD_DIR}/docker/n8n/workflows/"

# Copy runtime scripts
cp "${PROJECT_ROOT}/scripts/start.sh" "${TEMP_BUILD_DIR}/scripts/"
cp "${PROJECT_ROOT}/scripts/stop.sh" "${TEMP_BUILD_DIR}/scripts/"
cp "${PROJECT_ROOT}/scripts/setup-evolution.sh" "${TEMP_BUILD_DIR}/scripts/"
cp "${PROJECT_ROOT}/scripts/import-workflows.sh" "${TEMP_BUILD_DIR}/scripts/"
cp "${PROJECT_ROOT}/scripts/deploy.sh" "${TEMP_BUILD_DIR}/scripts/"
cp "${PROJECT_ROOT}/scripts/lib/common.sh" "${TEMP_BUILD_DIR}/scripts/lib/"

# Copy static configuration files
cp "${PROJECT_ROOT}/config/bot-config.json" "${TEMP_BUILD_DIR}/config/"
cp "${PROJECT_ROOT}/config/guardrails-rules.json" "${TEMP_BUILD_DIR}/config/"
cp "${PROJECT_ROOT}/config/notification-templates"/*.txt "${TEMP_BUILD_DIR}/config/notification-templates/"

# Copy quickstart to package root for immediate availability
cp "${PROJECT_ROOT}/specs/001-whatsapp-appointment-notifier/quickstart.md" "${TEMP_BUILD_DIR}/README.md"

# Generate package-manifest.json
log_info "Generating package manifest..."
SHA256_MFT_FILE="${TEMP_BUILD_DIR}/package-manifest.json"
cat <<EOF > "$SHA256_MFT_FILE"
{
  "version": "${VERSION}",
  "build_date": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "components": [
    "docker-compose.yml",
    "n8n-workflows",
    "evolution-api-config",
    "scripts",
    "config"
  ],
  "artifact_filename": "notifier-${VERSION}.tar.gz"
}
EOF

# Compress into self-contained tarball
log_info "Compressing artifacts into tarball archive..."
cd "$DIST_DIR"
TAR_FILE="notifier-${VERSION}.tar.gz"
tar -czf "$TAR_FILE" "notifier-${VERSION}"

# Calculate checksum
if command -v sha256sum &> /dev/null; then
  CHECKSUM=$(sha256sum "$TAR_FILE" | cut -d' ' -f1)
elif command -v shasum &> /dev/null; then
  CHECKSUM=$(shasum -a 256 "$TAR_FILE" | cut -d' ' -f1)
else
  CHECKSUM="Unavailable"
fi

# Append checksum to manifest inside dist (not inside tarball anymore)
echo "{\"sha256\": \"${CHECKSUM}\"}" > "${DIST_DIR}/checksum.txt"

# Cleanup temp assembly files
rm -rf "${TEMP_BUILD_DIR}"

log_success "Package created successfully!"
echo -e "--------------------------------------------------------"
log_info "Package Details:"
echo -e "  - Artifact:  ${DIST_DIR}/${TAR_FILE}"
echo -e "  - Size:      $(du -sh "$TAR_FILE" | cut -f1)"
echo -e "  - SHA256:    ${CHECKSUM}"
echo -e "--------------------------------------------------------"
