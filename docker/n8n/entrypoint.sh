#!/bin/sh
set -e

# n8n loads community packages from ~/.n8n/nodes/node_modules/<package-name>/
CUSTOM_DIR="/home/node/.n8n/nodes/node_modules/n8n-nodes-evolution-api"
N8N_WORKFLOW_SRC="/usr/local/lib/node_modules/n8n/node_modules/n8n-workflow"

# Ensure community package is installed in the persistent volume
if [ ! -d "$CUSTOM_DIR/dist" ]; then
  echo "[entrypoint] Installing Evolution API community node into persistent volume..."
  mkdir -p /home/node/.n8n/nodes/node_modules
  cp -r /opt/n8n-custom/n8n-nodes-evolution-api /home/node/.n8n/nodes/node_modules/
  cd "$CUSTOM_DIR"
  npm install --omit=dev --legacy-peer-deps --ignore-scripts
fi

# Ensure n8n-workflow peer dependency is symlinked (needed for the custom node to load)
if [ ! -e "$CUSTOM_DIR/node_modules/n8n-workflow" ]; then
  echo "[entrypoint] Linking n8n-workflow peer dependency..."
  mkdir -p "$CUSTOM_DIR/node_modules"
  ln -sf "$N8N_WORKFLOW_SRC" "$CUSTOM_DIR/node_modules/n8n-workflow"
fi

# Hand off to the original n8n entrypoint
exec n8n "$@"
