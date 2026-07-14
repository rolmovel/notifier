# Implementation Plan: WhatsApp Appointment Notifier

**Branch**: `001-whatsapp-appointment-notifier` | **Date**: 2026-07-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-whatsapp-appointment-notifier/spec.md`

## Summary

The system automates sending WhatsApp appointment-reminder notifications for a clinic. Staff upload an appointment file (CSV/Excel); n8n workflows parse, validate, and send personalized WhatsApp messages via Evolution API. An optional AI-powered bot responds to patient replies with strict clinical guardrails (no medical advice, no cross-patient data, appointment-only topics, automatic human escalation). The entire stack is packaged as Docker containers with automation scripts for build and deployment.

## Technical Context

**Language/Version**: Node.js 20+ (Evolution API runtime), n8n workflows (visual + JavaScript/Python code nodes), Bash (packaging scripts)

**Primary Dependencies**: n8n (workflow orchestration, v1.x), Evolution API v2.x (WhatsApp messaging via Baileys), PostgreSQL 16 (shared database for n8n + Evolution API), Redis 7 (Evolution API caching), Docker + Docker Compose (containerization)

**Storage**: PostgreSQL 16 — shared between n8n (workflow state, executions, credentials) and Evolution API (WhatsApp instances, message logs, session data). Redis for Evolution API caching layer.

**Testing**: n8n workflow test executions (manual + automated via n8n API), Evolution API health checks, Docker Compose integration tests, Bash script validation with `shellcheck`

**Target Platform**: Linux server (Docker host) — any environment supporting Docker Engine and Docker Compose

**Project Type**: Containerized automation platform (Docker Compose multi-service stack with orchestration workflows)

**Performance Goals**: Process and send up to 100 appointment notifications within 5 minutes; bot response latency < 10 seconds per message

**Constraints**: All services must run within Docker containers; configuration must be externalized via `.env` files (no rebuild needed for config changes); bot must never provide medical advice (hard guardrail); patient data isolation enforced per-conversation

**Scale/Scope**: Single clinic, up to 500 appointments/day, single WhatsApp number, single n8n instance

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution file at `.specify/memory/constitution.md` is in template form (unfilled placeholders). No custom principles, constraints, or governance rules have been defined by the project owner.

**Gate evaluation**: PASS (conditionally) — No constitution principles exist to violate. The project proceeds with default best-practice principles:
- **Simplicity**: Start with the minimal viable Docker Compose stack; avoid premature complexity (no Kubernetes, no message queues beyond what Evolution API requires internally).
- **Configuration externalization**: All environment-specific settings via `.env` files.
- **Guardrails-first**: Bot safety guardrails are non-negotiable and implemented before any bot response capability goes live.

> **Note**: If the project owner defines a constitution later, re-evaluate this plan against those principles.

### Post-Design Re-Evaluation (Phase 1 Complete)

After completing Phase 1 design (research.md, data-model.md, contracts/, quickstart.md), the constitution check is re-evaluated:

**Gate evaluation**: PASS — No constitution violations. The design artifacts adhere to the default best-practice principles:
- **Simplicity**: The 4-service Docker Compose stack (PostgreSQL, Redis, Evolution API, n8n) remains minimal. No additional infrastructure was introduced during design.
- **Configuration externalization**: All configurable values (API keys, bot settings, guardrail rules, notification templates, business hours) are externalized to `.env` and `config/` files.
- **Guardrails-first**: The bot guardrails contract defines a 4-layer safety system (topic classification, constrained AI generation, post-generation validation, escalation routing) that must be fully implemented before the bot is enabled (`BOT_ENABLED=false` by default in `.env.example`).
- **Audit/logging**: All conversations and notification results are logged in PostgreSQL with configurable retention, satisfying the audit requirement (FR-017).

## Project Structure

### Documentation (this feature)

```text
specs/001-whatsapp-appointment-notifier/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── evolution-api-contract.md    # Evolution API endpoints used
│   ├── n8n-webhook-contract.md      # n8n webhook endpoints for Evolution API callbacks
│   ├── appointment-file-schema.md   # CSV/Excel file format contract
│   └── bot-guardrails-contract.md   # Bot response rules and escalation contract
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
docker/
├── docker-compose.yml           # Main orchestration: n8n + Evolution API + PostgreSQL + Redis
├── docker-compose.override.yml  # Local development overrides (optional)
├── .env.example                  # Template for all environment variables
├── n8n/
│   ├── Dockerfile                # Custom n8n image with pre-imported workflows
│   └── workflows/                # Exported n8n workflow JSON files
│       ├── send-appointments.json    # P1: File upload → parse → send notifications
│       ├── receive-reply.json        # P2: Webhook → guardrails → bot response
│       └── health-check.json         # Service health monitoring
├── evolution-api/
│   └── evolution.env             # Evolution API specific env vars (referenced by compose)
├── postgres/
│   └── init/                     # SQL init scripts (if needed beyond Prisma migrations)
└── redis/
    └── redis.conf                # Redis configuration (if customization needed)

scripts/
├── build.sh                     # Build all Docker images and prepare deployment artifact
├── deploy.sh                    # Deploy the packaged artifact on target environment
├── start.sh                     # Start all services (wrapper around docker compose up)
├── stop.sh                      # Stop all services (wrapper around docker compose down)
├── package.sh                   # Create self-contained tar.gz deployment artifact
├── import-workflows.sh          # Import n8n workflow JSONs via n8n REST API
├── setup-evolution.sh           # Initialize Evolution API instance and configure webhook
└── lib/
    └── common.sh                # Shared bash functions (logging, color output, validation)

config/
├── notification-templates/      # Message template files (externalized, no rebuild needed)
│   ├── appointment-reminder.txt     # Default reminder template
│   └── appointment-reminder-es.txt # Spanish variant
├── bot-config.json              # Bot enable/disable, allowed topics, escalation rules, business hours
└── guardrails-rules.json        # Topic classification rules, blocked categories, response limits

docs/
├── architecture.md              # System architecture overview with diagrams
├── deployment-guide.md          # Step-by-step deployment instructions
└── bot-guardrails.md            # Guardrail design and safety documentation
```

**Structure Decision**: A containerized multi-service project structure was selected. The `docker/` directory holds all Docker Compose configuration and service-specific files. The `scripts/` directory contains all automation scripts for building, packaging, and deploying. The `config/` directory holds externalized configuration (templates, bot settings, guardrail rules) that can be modified without rebuilding Docker images. The `docs/` directory holds architecture and deployment documentation. This structure cleanly separates infrastructure, automation, configuration, and documentation.

## Complexity Tracking

> No constitution violations to justify. The architecture uses the minimum number of services required: n8n (orchestration), Evolution API (WhatsApp), PostgreSQL (shared storage), Redis (Evolution API caching). No additional message queues, API gateways, or reverse proxies are included in the initial version.
