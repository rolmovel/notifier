# Deployment & Operations Guide: WhatsApp Appointment Notifier

This document outlines the hosting environment requirements, installation steps, backup patterns, and troubleshooting procedures for deploying the **WhatsApp Appointment Notifier** system in a production environment.

---

## 💻 1. Target Hardware & Operating System Requirements

### Recommended Host Specs
* **Virtualization**: Compatible virtualization host (DigitalOcean, AWS, Linode, AWS EC2, or a dedicated on-premise local server).
* **OS**: Ubuntu 22.04 LTS or 24.04 LTS (highly recommended), Debian 12, or any Linux kernel supporting Docker Engine v24+.
* **RAM**: 2 GB Minimum (4 GB Recommended to allow ample headrooms for the n8n visual workflows engine and model execution concurrency).
* **CPU**: Dual-core processor or vCPU.
* **Disk**: 20 GB of available SSD storage space (persistent volumes for logs and relational databases).

### Network Configuration Requirements
* Outbound internet access is required on the host to connect with WhatsApp servers (via Evolution API) and OpenAI APIs (via n8n).
* Inbound ports configuration:
  * Port **5678** (or custom `N8N_PORT`) must be accessible if clinic staff need to interact with the n8n dashboard externally. Use standard HTTPS reverse proxying (e.g. Nginx + Let's Encrypt) in production!
  * Port **8080** (or custom `EVOLUTION_API_PORT`) does not need to be accessible from the public WAN — it only requires internal Docker Network bridge access.

---

## 📦 2. Production Deployment Steps (Self-Contained Release)

When deploying on a fresh production server, follow these 5 steps directly using our packaged deployment archive:

### Step 1: Transfer and Extract the Package
Copy the compiled release archive `notifier-1.0.0.tar.gz` (produced by `./scripts/package.sh`) to the target host and extract:

```bash
tar -xzf notifier-1.0.0.tar.gz
cd notifier-1.0.0
```

### Step 2: Configure Environment Variables
Copy the configuration template and open it with your favorite editor (e.g., `nano`):

```bash
cp docker/.env.example docker/.env
nano docker/.env
```

Review and configure the mandatory production values:
* **POSTGRES_PASSWORD**: Change the template key to a secure 32-character string.
* **N8N_ENCRYPTION_KEY**: Set a long, random string to encrypt credentials inside the database.
* **EVOLUTION_API_KEY**: Change this key to lock the Evolution API endpoints (protects outbound WhatsApp messaging).
* **OPENAI_API_KEY** (Ensure you configure standard credentials in the n8n nodes or env to allow GPT connections!)

### Step 3: Run Deployment Script
Run the robust automated setup:

```bash
./scripts/deploy.sh
```

This automated deployment script will:
1. Verify permissions of all utility scripts.
2. Check that Docker and Docker Compose v2+ are installed.
3. Spin up the 4 services (PostgreSQL, Redis, Evolution API, and n8n) in background mode.
4. Inject and import all pre-packaged workflows JSON files directly into the active n8n service.

### Step 4: Scan the WhatsApp Connection QR Code
Launch the session configuration script to generate a WhatsApp web link and display connection details:

```bash
./scripts/setup-evolution.sh
```

Grab your clinic mobile phone, go to **Dispositivos Vinculados (Linked Devices)** inside WhatsApp, and scan the QR code displayed in your terminal. Once linked, the connection is active.

### Step 5: Activate Workflows in n8n UI
1. Navigate to the n8n admin panel (e.g., `http://your-server-ip:5678`).
2. Log in (or create the initial administrator user on first boot).
3. Click on the **Workflows** folder. You will see both pre-imported workflows:
   * **Send Appointment Notifications**
   * **Receive Patient Reply & Bot Response**
4. Make sure both are toggled to **Active** (green indicator).

---

## 🔄 3. Backup and Recovery Strategies

To safeguard data against server failures, back up these key assets daily:

### PostgreSQL Core Backup (Transactional Data)
Run a backup of the Postgres container using pg_dump:

```bash
docker exec -t notifier-postgres pg_dumpall -U notifier > /backups/postgres_raw_backup_$(date +%F).sql
```

### Configuration Files Backup
Back up active settings files:
* `docker/.env`
* `config/bot-config.json`
* `config/guardrails-rules.json`

---

## 🛠️ 4. Active Operations & Diagnostics Commands

| Purpose | Complete Command |
|---|---|
| View active container health | `docker compose -f docker/docker-compose.yml ps` |
| Read n8n workflow system logs | `docker compose -f docker/docker-compose.yml logs n8n --tail=100 -f` |
| Read WhatsApp Gateway logs | `docker compose -f docker/docker-compose.yml logs evolution-api --tail=100 -f` |
| View DB status | `docker exec -it notifier-postgres pg_isready -U notifier` |
| Stop all services safely | `./scripts/stop.sh` |
| Start all services safely | `./scripts/start.sh` |
| Force database re-schema init | `docker compose -f docker/docker-compose.yml down -v && ./scripts/start.sh` |
