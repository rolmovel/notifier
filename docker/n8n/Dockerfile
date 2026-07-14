# ==============================================================================
# Custom n8n Image with Pre-configured Mounting Points
# ==============================================================================
FROM n8nio/n8n:1.44.1

# Switch to root to create configuration directories
USER root

# Create mount point for custom clinic configurations (templates, bot config)
RUN mkdir -p /opt/notifier/config && \
    chown -R node:node /opt/notifier

# Stage Evolution API community node to a persistent location.
# n8n loads community packages from ~/.n8n/nodes/node_modules/<package-name>/
# The entrypoint script copies it there on first boot (since that directory
# is inside a Docker volume and gets overwritten by the volume mount on
# subsequent starts).
RUN mkdir -p /opt/n8n-custom && \
    cd /tmp && \
    npm pack n8n-nodes-evolution-api --pack-destination /tmp && \
    tar xzf n8n-nodes-evolution-api-*.tgz && \
    cp -r package /opt/n8n-custom/n8n-nodes-evolution-api && \
    cd /opt/n8n-custom/n8n-nodes-evolution-api && \
    npm install --omit=dev --legacy-peer-deps --ignore-scripts && \
    rm -rf /tmp/package /tmp/n8n-nodes-evolution-api-*.tgz

# Copy custom entrypoint that ensures community packages are linked on every boot
COPY n8n/entrypoint.sh /custom-entrypoint.sh
RUN chmod +x /custom-entrypoint.sh && chown node:node /custom-entrypoint.sh

# Switch back to node user for security
USER node

# Expose default n8n port
EXPOSE 5678

ENTRYPOINT ["/custom-entrypoint.sh"]
