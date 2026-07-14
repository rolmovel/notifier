# Quickstart: WhatsApp Appointment Notifier

**Date**: 2026-07-13
**Feature**: 001-whatsapp-appointment-notifier

## Prerequisites

- Docker Engine 24+ and Docker Compose v2+ installed on the host machine
- A WhatsApp number with an active account (phone with WhatsApp installed for QR scanning)
- At least 2GB of available RAM for the Docker stack

## Quick Start (5 Steps)

### Step 1: Clone and Configure

```bash
git clone <repository-url> notifier
cd notifier
cp docker/.env.example docker/.env
```

Edit `docker/.env` and set the following required variables:

```env
# PostgreSQL
POSTGRES_USER=notifier
POSTGRES_PASSWORD=change-me-strong-password
POSTGRES_DB=notifier
POSTGRES_DB_N8N=n8n
POSTGRES_DB_EVOLUTION=evolution

# n8n
N8N_HOST=localhost
N8N_PORT=5678
N8N_PROTOCOL=http
WEBHOOK_URL=http://localhost:5678/
GENERIC_TIMEZONE=Europe/Madrid
TZ=Europe/Madrid

# Evolution API
EVOLUTION_API_URL=http://evolution-api:8080
EVOLUTION_API_KEY=change-me-evolution-api-key
EVOLUTION_INSTANCE_NAME=clinic-notifier

# Bot Configuration
BOT_ENABLED=false
BOT_LANGUAGE=es
DEFAULT_COUNTRY_CODE=+34

# Bot Memory
MAX_CONTEXT_MESSAGES=10
ENABLE_CROSS_APPOINTMENT_MEMORY=true
PROFILE_MEMORY_RETENTION_DAYS=90
SESSION_EXPIRY_HOURS=72
```

### Step 2: Build and Start

```bash
# Build images and start all services
./scripts/build.sh
./scripts/start.sh
```

Wait for all services to be healthy (typically 30-60 seconds):

```bash
docker compose ps
```

### Step 3: Initialize Evolution API (WhatsApp Connection)

```bash
# Create a WhatsApp instance and display QR code for scanning
./scripts/setup-evolution.sh
```

Scan the QR code with your WhatsApp mobile app (Settings → Linked Devices → Link a Device).

Verify the connection:

```bash
curl -H "apikey: change-me-evolution-api-key" \
  http://localhost:8080/instance/connectionState/clinic-notifier
```

The response should show `"state": "open"`.

### Step 4: Import n8n Workflows

```bash
# Import all workflow JSON files into n8n
./scripts/import-workflows.sh
```

Open the n8n UI at `http://localhost:5678` and:
1. Complete the initial n8n setup (create admin account)
2. Verify the imported workflows appear in the Workflows list
3. Activate both workflows (toggle the "Active" switch)

### Step 5: Send Your First Notification

Create a test CSV file (`test-appointments.csv`):

```csv
patient_name,patient_phone,appointment_date,appointment_time,appointment_type
Juan Test,+34612345678,2026-07-20,14:30,Consulta general
```

Upload and send:

```bash
curl -X POST \
  -H "X-API-Key: your-n8n-api-key" \
  -F "file=@test-appointments.csv" \
  http://localhost:5678/webhook/upload-appointments
```

Check results:

```bash
# Replace BATCH_ID with the batchId from the upload response
curl -H "X-API-Key: your-n8n-api-key" \
  http://localhost:5678/webhook/notification-results/BATCH_ID
```

## Enabling the Bot

To enable the automated response bot:

1. Edit `config/bot-config.json`:
   ```json
   {
     "enabled": true,
     "language": "es",
     "business_hours_start": "09:00",
     "business_hours_end": "18:00",
     "business_hours_timezone": "Europe/Madrid"
   }
   ```

2. Restart the n8n workflow (deactivate and reactivate in n8n UI, or restart the container):
   ```bash
   docker compose restart n8n
   ```

3. Test by replying to a notification message from the patient's WhatsApp.

## Packaging for Deployment

To create a self-contained deployment artifact:

```bash
./scripts/package.sh
# Output: dist/notifier-1.0.0.tar.gz
```

Deploy on a target machine:

```bash
# Copy the artifact to the target machine
scp dist/notifier-1.0.0.tar.gz user@target:~/

# On the target machine
tar xzf notifier-1.0.0.tar.gz
cd notifier-1.0.0
cp docker/.env.example docker/.env
# Edit docker/.env with production values
./scripts/deploy.sh
```

## Common Operations

| Operation | Command |
|-----------|---------|
| Start all services | `./scripts/start.sh` |
| Stop all services | `./scripts/stop.sh` |
| Check service status | `docker compose ps` |
| View n8n logs | `docker compose logs n8n -f` |
| View Evolution API logs | `docker compose logs evolution-api -f` |
| Restart n8n | `docker compose restart n8n` |
| Update notification template | Edit `config/notification-templates/appointment-reminder.txt` |
| Update bot configuration | Edit `config/bot-config.json` |
| Update guardrail rules | Edit `config/guardrails-rules.json` |
| Re-import workflows | `./scripts/import-workflows.sh` |

## Troubleshooting

### WhatsApp not connected
- Check Evolution API logs: `docker compose logs evolution-api`
- Re-run `./scripts/setup-evolution.sh` to generate a new QR code
- Ensure the phone has an active internet connection

### Notifications not sending
- Verify the n8n workflow is activated (green toggle in n8n UI)
- Check Evolution API connection status (Step 3)
- Review n8n execution logs for error details
- Verify the phone numbers in the CSV are in international format with `+` prefix

### Bot not responding
- Check `bot-config.json` has `"enabled": true`
- Verify the Evolution API webhook is configured (run `./scripts/setup-evolution.sh` again)
- Check business hours — the bot only responds during configured hours
- Review guardrail logs — messages may have been escalated instead of answered

### Port conflicts
- If port 5678 (n8n) or 8080 (Evolution API) is in use, modify the port mappings in `docker-compose.yml`
