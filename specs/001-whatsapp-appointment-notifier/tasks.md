---

description: "Task list for WhatsApp Appointment Notifier feature implementation"
---

# Tasks: WhatsApp Appointment Notifier

**Input**: Design documents from `specs/001-whatsapp-appointment-notifier/`

**Prerequisites**: [plan.md](plan.md) (required), [spec.md](spec.md) (required for user stories), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)

**Tests**: Tests are optional and manual or n8n workflow-driven for this project. They are detailed under the "Independent Test" criteria for each User Story.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- All configurations, workflows, and scripts are relative to the repository root.
- Docker settings: `docker/`
- Workflows: `docker/n8n/workflows/`
- Scripts: `scripts/`
- Static configurations: `config/`
- Documentation: `docs/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure.

- [x] T001 Create project directories config, scripts, docker, docs, specs per plan in `docker/`, `scripts/`, `config/`, `docs/`, `specs/`
- [x] T002 Initialize dotenv configuration template in `docker/.env.example`
- [x] T003 [P] Create repository-wide gitignore file for local configuration files in `.gitignore`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core container infrastructure that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete and all containers can be spun up cleanly.

- [x] T004 Setup Docker Compose configuration with PostgreSQL, Redis, n8n, and Evolution API services in `docker/docker-compose.yml`
- [x] T005 Configure Evolution API environment variables in `docker/evolution-api/evolution.env`
- [x] T006 [P] Create PostgreSQL database initialization scripts for schemas in `docker/postgres/init/01-init-db.sql`
- [x] T007 Configure custom n8n Docker image setting up execution environment in `docker/n8n/Dockerfile`
- [x] T008 [P] Initialize helper script for logging and environment checking in `scripts/lib/common.sh`
- [x] T009 Create service management scripts to start/stop the Docker containers in `scripts/start.sh` and `scripts/stop.sh`

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - Upload Appointment File & Send Notifications (Priority: P1) 🎯 MVP

**Goal**: Allow clinic staff to upload CSV/XLSX appointment files, parse them, validate data, and send WhatsApp notifications via Evolution API with retry logic and immediate result reports.

**Independent Test**: POST a valid appointment file to n8n upload webhook, verify WhatsApp notifications are received on test numbers, and GET batch results using the batch ID of the upload.

### Implementation for User Story 1

- [x] T010 [P] [US1] Create appointment reminder text message templates in `config/notification-templates/appointment-reminder.txt`
- [x] T011 [P] [US1] Define database schema table scripts for Appointments and Notification Records in `docker/postgres/init/02-appointments-schema.sql`
- [x] T012 [US1] Implement Appointment upload, parsing, and normalization logic in `docker/n8n/workflows/send-appointments.json` (Part 1 - Webhook & Parse)
- [x] T013 [US1] Devise database operations for storing parsed batch appointments in PostgreSQL inside `docker/n8n/workflows/send-appointments.json` (Part 2 - DB Store)
- [x] T014 [US1] Implement Evolution API sending block with batch processing and delay of 1200ms in `docker/n8n/workflows/send-appointments.json` (Part 3 - REST Sender)
- [x] T015 [US1] Add exponential backoff retry loop (3 retries: 5s, 15s, 45s) for WhatsApp delivery failures in `docker/n8n/workflows/send-appointments.json` (Part 4 - Retry Block)
- [x] T016 [US1] Add GET results endpoint logic returning batch summaries and validation failures in `docker/n8n/workflows/send-appointments.json` (Part 5 - Reports Webhook)
- [x] T017 [US1] Write automated schema validation code for incoming files in `docker/n8n/workflows/send-appointments.json` (Part 6 - Schema Check)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently.

---

## Phase 4: User Story 2 - Automated WhatsApp Response Bot with Guardrails (Priority: P2)

**Goal**: An automated response bot with Level 1 (per-appointment) and Level 2 (cross-appointment) memories that responds to patient replies with strict 4-layer medical guardrails and staff escalation.

**Independent Test**: Simulate incoming WhatsApp replying to a notification asking about date/time (bot answers using memory context) and then asking about symptoms (bot refuses and escalates).

### Implementation for User Story 2

- [x] T018 [P] [US2] Create bot configuration JSON with allowed topics, metadata and business hours in `config/bot-config.json`
- [x] T019 [P] [US2] Create guardrail rules configuration including medical terms blocklist in `config/guardrails-rules.json`
- [x] T020 [P] [US2] Create database schema for ConversationSession, PatientProfile, and PatientReply in `docker/postgres/init/03-bot-schema.sql`
- [x] T021 [US2] Implement Layer 1 Topic Classification (Pre-Response AI classification) in `docker/n8n/workflows/receive-reply.json`
- [x] T022 [US2] Create n8n Logic for retrieving and creating Level 1 ConversationSession memory in `docker/n8n/workflows/receive-reply.json`
- [x] T023 [US2] Create n8n Logic for retrieving and updating Level 2 PatientProfile cross-appointment memory in `docker/n8n/workflows/receive-reply.json`
- [x] T024 [US2] Implement Layer 2 Response Generation (Constrained AI Agent) with context window in `docker/n8n/workflows/receive-reply.json`
- [x] T025 [US2] Implement Layer 3 Response Validation (medical blocklist scan and cross-patient check) in `docker/n8n/workflows/receive-reply.json`
- [x] T026 [US2] Implement Layer 4 Escalation routing mechanism to notify clinic staff in `docker/n8n/workflows/receive-reply.json`
- [x] T027 [US2] Implement business hours checker node routing out-of-hours messages to bot holding in `docker/n8n/workflows/receive-reply.json`

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently.

---

## Phase 5: User Story 3 - Packaging & Deployment Automation (Priority: P3)

**Goal**: Package the system into a single production-ready deployments archive with setup commands and automatic workflows importing.

**Independent Test**: Run packaging script, verify `tar.gz` is created under `dist/`, unzip on a blank machine, run setup and verify stack starts cleanly.

### Implementation for User Story 3

- [x] T028 [US3] Create setup-evolution script to initialize WhatsApp instance and set webhook in `scripts/setup-evolution.sh`
- [x] T029 [US3] Create workflow import script utilizing n8n REST API to sync json files in `scripts/import-workflows.sh`
- [x] T030 [US3] Implement packaging script compiling Compose, workflows, configuration and scripts in `scripts/package.sh`
- [x] T031 [US3] Implement deploy script that automates unpacking and starting services on the production host in `scripts/deploy.sh`
- [x] T032 [P] [US3] Create a system health check workflow mapping container health statuses in `docker/n8n/workflows/health-check.json`

**Checkpoint**: All user stories should now be independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and full system verification.

- [x] T033 [P] Document system architecture, Docker layouts, and n8n workflow diagrams in `docs/architecture.md`
- [x] T034 [P] Create full packaging, server requirements, and setup manual in `docs/deployment-guide.md`
- [x] T035 [P] Create bot documentation detailing prompt designs and guardrails enforcement in `docs/bot-guardrails-contract.md`
- [x] T036 Run quickstart validation against a simulated environment using `specs/001-whatsapp-appointment-notifier/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories.
- **User Stories (Phase 3+)**: All depend on Foundational phase completion.
  - User stories can then proceed in parallel if team capacity allows.
  - Or sequentially in priority order (P1 → P2 → P3).
- **Polish (Final Phase)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories.
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Uses the same Postgres container setup, and matches reply numbers against processed appointments from US1, but the bot flow operates on its own webhook trigger.
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Automates setup of features created in US1 and US2, can be tested iteratively.

### Within Each User Story

- Schema/config files first.
- Inner n8n logic steps (e.g. parse files and load DB) before external integration calls (Evolution API).
- AI agent prompt configuration before secondary post-validation logic.
- Service is fully complete and testable before entering the next prioritized story.

### Parallel Opportunities

- All Setup tasks marked `[P]` can run in parallel.
- Database schema scripts `[P]` in US1 and US2 can be prepared in parallel with config structures.
- Once Foundation is complete, developers can split:
  - Developer A builds Story 1 (sending engine workflows)
  - Developer B builds Story 2 (reply bot workflows and configuration rules)
- Documentation tasks `[P]` can run in parallel while other tasks are undergoing review or validation.

---

## Parallel Example: User Story 1 & 2 DB Prep

```bash
# Launch database schema scripts development together:
Task: "Define database schema table scripts for Appointments and Notification Records in docker/postgres/init/02-appointments-schema.sql"
Task: "Create database schema for ConversationSession, PatientProfile, and PatientReply in docker/postgres/init/03-bot-schema.sql"

# Launch bot static configs together:
Task: "Create bot configuration JSON with allowed topics, metadata and business hours in config/bot-config.json"
Task: "Create guardrail rules configuration including medical terms blocklist in config/guardrails-rules.json"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (P1 - Core Sending Engine)
4. **STOP and VALIDATE**: Upload file, verify message delivery, confirm results returned.
5. Deploy/demo if ready.

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready.
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!).
3. Add User Story 2 → Test replies and memory/guardrails independently → Deploy/Demo.
4. Add User Story 3 → Test packaging and target machine restoration → Deploy/Demo.
5. Each story adds value without breaking previous stories.
