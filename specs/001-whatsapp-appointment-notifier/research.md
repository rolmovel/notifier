# Research: WhatsApp Appointment Notifier

**Date**: 2026-07-13
**Feature**: 001-whatsapp-appointment-notifier

## Research Tasks

### R-001: n8n Docker Deployment Best Practices

**Decision**: Use the official `docker.n8n.io/n8nio/n8n` Docker image with Docker Compose, PostgreSQL as the database backend (not SQLite), and persistent volumes for workflow data.

**Rationale**: n8n's official Docker Hub documentation recommends Docker Compose with PostgreSQL for production deployments. SQLite is the default but does not support concurrent executions reliably. PostgreSQL provides better durability for workflow execution history and credentials. The `/home/node/.n8n` volume must always be persisted (contains encryption key for credentials). Environment variables `DB_TYPE=postgresdb` with connection parameters configure the database. Timezone is set via `GENERIC_TIMEZONE` and `TZ` environment variables (critical for scheduled notifications).

**Alternatives considered**:
- SQLite (simpler, fewer containers) — rejected for production reliability concerns and concurrent execution limitations.
- n8n Cloud (managed) — rejected because the user wants everything packaged for Docker self-hosting.
- Kubernetes deployment — rejected as premature complexity for a single-clinic scope.

---

### R-002: Evolution API Integration with n8n

**Decision**: Use Evolution API v2.x (`evoapicloud/evolution-api:latest` Docker image) with the Baileys-based WhatsApp Web connection. n8n communicates with Evolution API via HTTP Request nodes (REST API calls). Evolution API sends incoming message webhooks to n8n's Webhook node endpoint.

**Rationale**: Evolution API is a production-ready REST API for WhatsApp messaging. It supports both Baileys (free, WhatsApp Web-based) and WhatsApp Cloud API (official, paid per message). For a clinic with moderate volume, the Baileys connection is cost-effective and sufficient. Evolution API requires:
- PostgreSQL database (can share n8n's PostgreSQL instance with a separate schema/database)
- Redis for caching (recommended)
- API key authentication via `apikey` header
- Webhook configuration for receiving incoming messages

n8n integrates with Evolution API via HTTP Request nodes (POST to `/instance/sendText` for sending messages, webhook listener for incoming messages). Evolution API's architecture diagram shows native n8n integration support.

**Alternatives considered**:
- WhatsApp Cloud API (official Meta API) — available through Evolution API as a connection type, but requires Meta Business verification and has per-message costs. Can be configured later without architecture change.
- Direct Baileys library integration in n8n code nodes — rejected as it bypasses Evolution API's session management, reconnection logic, and media handling.
- Typebot for bot responses — rejected to keep the architecture simpler; n8n's AI Agent nodes can handle bot logic with guardrails directly.

---

### R-003: Bot Guardrails Architecture for Clinical Context

**Decision**: Implement a multi-layer guardrail system within n8n workflows using:
1. **Topic classification** (AI Agent node with system prompt restricting to appointment-related topics)
2. **Content filtering** (pre-response validation checking for medical terms, medication names, symptoms)
3. **Response validation** (post-generation check before sending via Evolution API)
4. **Escalation routing** (automatic notification to clinic staff when guardrails are triggered)

**Rationale**: The spec requires strict guardrails: no medical advice (FR-012), no cross-patient data (FR-013), appointment-only topics (FR-014), and mandatory escalation (FR-015). A single layer is insufficient — an AI model might produce medical advice despite instructions. The multi-layer approach ensures:
- Layer 1 (classification): Determines if the patient's message is appointment-related. If not, escalate immediately.
- Layer 2 (content filtering): Scans the AI-generated response for medical terms, medication names, diagnostic language. If detected, block and escalate.
- Layer 3 (validation): Final check that the response only references the specific patient's appointment data (no other patient information leaks).
- Layer 4 (escalation): When any layer triggers, send a notification to clinic staff (via a separate n8n workflow or message queue) and inform the patient.

The guardrail rules are externalized in `config/guardrails-rules.json` so they can be tuned without redeploying containers.

**Alternatives considered**:
- Single system prompt approach — rejected as insufficient for medical context where errors have liability implications.
- External guardrail service (e.g., NeMo Guardrails) — rejected to avoid adding another service; n8n's built-in AI nodes with custom validation logic are sufficient.
- Human-in-the-loop for all bot responses — rejected as it defeats the purpose of automation; only escalated messages require human review.

---

### R-004: Appointment File Parsing in n8n

**Decision**: Use n8n's built-in file parsing capabilities. For CSV files, use the "Extract from File" node (or the Spreadsheet File node). For Excel/XLSX files, use the Spreadsheet File node which supports `.xlsx` format. The file is uploaded via an n8n Webhook node (POST with multipart/form-data) or placed in a watched directory.

**Rationale**: n8n has native nodes for parsing CSV and Excel files without custom code. The Spreadsheet File node handles both `.csv` and `.xlsx` formats. The Webhook node supports binary data (file uploads) via the "Binary Property" option. After parsing, each row becomes an n8n item that flows through the workflow for validation and sending.

**Alternatives considered**:
- Custom Python code node for parsing — unnecessary since n8n's built-in nodes handle standard formats.
- Google Sheets integration — adds external dependency; the spec requires file upload.
- Pre-processing script before n8n — rejected to keep all logic within n8n workflows for maintainability.

---

### R-005: Docker Compose Multi-Service Architecture

**Decision**: Use a single `docker-compose.yml` with four services:
1. `postgres` — PostgreSQL 16 (shared by n8n and Evolution API)
2. `redis` — Redis 7 (for Evolution API caching)
3. `evolution-api` — Evolution API v2.x (WhatsApp messaging)
4. `n8n` — n8n (workflow orchestration)

All services on a single Docker network. Environment variables externalized in `.env` file. Volumes for PostgreSQL data, Redis data, n8n data, and Evolution API data.

**Rationale**: The minimum viable stack requires these four services. PostgreSQL can be shared between n8n and Evolution API (different databases within the same instance) to reduce resource usage. Redis is required by Evolution API for caching. No reverse proxy (Nginx/Traefik) is included in the initial version — services are accessed directly on their ports. A reverse proxy can be added later for production TLS termination.

**Alternatives considered**:
- Separate PostgreSQL instances for n8n and Evolution API — rejected as unnecessary resource overhead for single-clinic scale.
- Include Nginx reverse proxy — deferred to a future enhancement; not needed for MVP.
- Include MinIO for media storage — deferred; Evolution API can use local storage initially.

---

### R-006: Packaging and Deployment Automation Scripts

**Decision**: Create Bash scripts (`scripts/` directory) for:
- `build.sh` — Builds custom Docker images (if any) and pulls required images
- `package.sh` — Creates a self-contained `tar.gz` artifact with all configs, workflows, scripts, and a `docker-compose.yml`
- `deploy.sh` — Extracts the artifact on a target machine and runs `docker compose up -d`
- `start.sh` / `stop.sh` — Wrappers for `docker compose up -d` / `docker compose down`
- `import-workflows.sh` — Uses n8n's REST API to import workflow JSON files
- `setup-evolution.sh` — Creates a WhatsApp instance in Evolution API and configures the webhook URL to point to n8n

**Rationale**: The user explicitly requested packaging automation scripts. Bash is the simplest scripting language for Docker orchestration on Linux. The scripts use `docker compose` commands and `curl` for API calls. The `package.sh` script creates a versioned `tar.gz` that can be transferred to any Docker-capable host. All scripts share common functions via `scripts/lib/common.sh`.

**Alternatives considered**:
- Make instead of Bash scripts — rejected; Bash is more readable for Docker operations and doesn't require a build system.
- Docker Swarm or Kubernetes manifests — rejected as premature for single-node deployment.
- Ansible playbooks — rejected to avoid adding a dependency; Bash scripts are sufficient for the scope.

---

### R-007: n8n Workflow Design for Notification Sending

**Decision**: Design two primary n8n workflows:

**Workflow 1: Send Appointment Notifications (P1)**
- Trigger: Webhook node (receives file upload via POST multipart/form-data) OR manual trigger with file path
- Parse: Spreadsheet File node (extracts rows from CSV/XLSX)
- Validate: Code node (validates required fields: name, phone, date, time, type; normalizes phone numbers)
- Split: Splits valid and invalid records into two branches
- Send: HTTP Request node (POST to Evolution API `/instance/sendText` for each valid record)
- Retry: Loop node with exponential backoff for failed sends (3 retries: 5s, 15s, 45s)
- Report: Aggregate results, generate summary (total, sent, failed, pending), return via webhook response or save to file

**Workflow 2: Receive Patient Reply & Bot Response (P2)**
- Trigger: Webhook node (receives Evolution API webhook for incoming messages)
- Lookup: HTTP Request node to query appointment data by phone number (from PostgreSQL or stored in n8n workflow variables)
- Guardrail Layer 1: AI Agent node classifies the message topic (appointment-related vs. other)
- Guardrail Layer 2: If appointment-related, AI Agent generates response using only the patient's appointment data
- Guardrail Layer 3: Code node validates response (no medical terms, no other patient data)
- Send: HTTP Request node sends response via Evolution API
- Escalate: If any guardrail triggers, send notification to staff (via separate webhook or message)

**Rationale**: n8n's visual workflow builder supports all required nodes: Webhook (trigger), Spreadsheet File (parse), Code (validation), HTTP Request (Evolution API calls), AI Agent (bot responses), and Loop (retry logic). The workflows are exported as JSON and imported during deployment via `import-workflows.sh`.

**Alternatives considered**:
- Single combined workflow — rejected for clarity and independent testability.
- External Python service for bot logic — rejected; n8n's AI Agent nodes with LangChain integration are sufficient and keep all logic in one place.
- Storing appointment data in a separate database table — considered; for MVP, data is stored in n8n's workflow execution context or a simple PostgreSQL table accessible via n8n's PostgreSQL node.
