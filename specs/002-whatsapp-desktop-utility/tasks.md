# Tasks: WhatsApp Desktop Utility

**Input**: Design documents from `/specs/002-whatsapp-desktop-utility/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: No tests are included — the feature specification does not explicitly request a TDD approach. Tests can be added later if requested.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `bridge/`, `tests/` at repository root
- Python application code lives in `src/` (models, services, ui, utils)
- Node.js Baileys bridge lives in `bridge/`
- Tests mirror source structure under `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependency management, and basic directory structure

- [X] T001 Create project directory structure per plan.md: `src/models/`, `src/services/`, `src/ui/`, `src/utils/`, `bridge/`, `tests/unit/`, `tests/integration/`, `tests/gui/`
- [X] T002 Create Python `requirements.txt` with dependencies: PySide6, openpyxl, httpx, pydantic, phonenumbers, platformdirs
- [X] T003 [P] Create Node.js `bridge/package.json` with dependencies: @whiskeysockets/baileys, express
- [X] T004 [P] Create `pyproject.toml` with project metadata, Python 3.11+ requirement, and dev dependencies (pytest, pytest-qt, pytest-httpx, pytest-asyncio)
- [X] T005 [P] Create `.gitignore` with Python venv, __pycache__, node_modules, bridge/auth/, dist/, build/, *.spec, .env

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 [P] Create Settings model in `src/models/settings.py` with fields: bridge_port (int, default 3001), default_country_code (str, default "+34"), message_template (str, default template), last_file_path (str | None) — per data-model.md
- [X] T007 [P] Create Appointment model in `src/models/appointment.py` with fields per data-model.md: row_number, start_time, duration_minutes, gabinete, patient_name, appointment_type, phone_landline, phone_mobile, phone_normalized (computed), is_valid (computed), validation_errors (computed) — include validation rules and phone selection logic
- [X] T008 [P] Create SendResult model in `src/models/send_result.py` with fields per data-model.md: appointment, status (enum sent/failed), phone_used, message_sent, sent_at, error_reason, api_response
- [X] T009 [P] Create SendSession model in `src/models/send_history.py` with fields per data-model.md: session_id, started_at, completed_at, source_file, total_appointments, valid_appointments, results — include computed properties: sent_count, failed_count, pending_count
- [X] T010 [P] Implement Excel column mapper in `src/utils/excel_column_mapper.py` — normalize header names (lowercase, strip accents, strip whitespace/punctuation), match against accepted names per excel-schema-contract.md, return canonical field → column index mapping
- [X] T011 [P] Implement phone normalizer in `src/services/phone_normalizer.py` — use `phonenumbers` library to normalize to E.164 format with configurable default country code, handle both national and international formats, return None if unparseable
- [X] T012 [P] Implement settings store in `src/services/settings_store.py` — load/save Settings model to JSON file in platformdirs config directory, create default settings on first run
- [X] T013 [P] Create Node.js Baileys bridge in `bridge/whatsapp-bridge.js` — Express server on 127.0.0.1:{port} with endpoints: GET /status (connection state), GET /qr (QR code string), POST /pair (phone number → pairing code), POST /send (number + text → message_id) — per whatsapp-bridge-contract.md, persist auth state to bridge/auth/

**Checkpoint**: Foundation ready — all models, utilities, and the bridge are in place. User story implementation can now begin.

---

## Phase 3: User Story 1 — Cargar Excel y Enviar Recordatorios (Priority: P1) 🎯 MVP

**Goal**: A clinic admin loads an Excel file with appointments, the app validates the data, sends WhatsApp reminders via the Baileys bridge, and displays a results report with sent/failed status.

**Independent Test**: Load an Excel with 5 valid appointments, connect WhatsApp via QR, click "Send Reminders", and verify the results table shows 5 messages sent (or corresponding failures if any phone is invalid).

### Implementation for User Story 1

- [X] T014 [P] [US1] Implement Excel reader in `src/services/excel_reader.py` — read .xlsx via openpyxl, use ExcelColumnMapper to find columns, parse rows into Appointment models, handle datetime/integer/string type coercion per excel-schema-contract.md, return list[Appointment] with validation errors per row
- [X] T015 [P] [US1] Implement template renderer in `src/services/template_renderer.py` — replace {{patient_name}}, {{appointment_date}}, {{appointment_time}}, {{appointment_type}}, {{gabinete}} variables in template string with Appointment data, handle missing variables gracefully (leave blank with warning)
- [X] T016 [US1] Implement WhatsApp client in `src/services/whatsapp_client.py` — httpx async client calling bridge endpoints (GET /status, POST /send), parse responses per whatsapp-bridge-contract.md, implement retry strategy for transient errors (429, 502, 503, 504) with exponential backoff (5s, 10s, 20s, max 3 retries), return SendResult for each send attempt
- [X] T017 [US1] Implement bridge manager in `src/services/bridge_manager.py` — start Node.js bridge subprocess (node bridge/whatsapp-bridge.js --port {port}), poll GET /status until responsive (max 10s timeout), stop subprocess on app exit (SIGTERM), detect if bridge is already running
- [X] T018 [US1] Implement send worker (QThread) in `src/services/send_worker.py` — receive list[Appointment], iterate calling WhatsAppClient.send() for each valid appointment, emit progress(int current, int total) signal, emit result_ready(SendResult) signal, emit finished(list[SendResult]) signal, support cancellation via cancel flag, 1200ms delay between sends
- [X] T019 [US1] Implement results table widget in `src/ui/results_table.py` — QTableWidget showing: patient name, phone, appointment date/time, status (✅ Sent / ❌ Failed), error reason; update in real-time as SendResult signals arrive
- [X] T020 [US1] Implement QR dialog in `src/ui/qr_dialog.py` — QDialog displaying QR code image (render qr_code string as QR image via qrcode library or QPixmap), "Refresh QR" button, auto-close when connection established (state: open), show pairing code alternative
- [X] T021 [US1] Implement main window in `src/ui/main_window.py` — QMainWindow with: "Select Excel File" button (QFileDialog), appointment preview table, "Send Reminders" button, progress bar, results table widget, "Export to CSV" button; wire SendWorker signals to UI updates; check WhatsApp connection before sending (show QrDialog if state: close)
- [X] T022 [US1] Implement CSV export in `src/services/csv_exporter.py` — export list[SendResult] to CSV file with columns: patient_name, phone, appointment_date, appointment_time, status, error_reason, sent_at
- [X] T023 [US1] Create application entry point in `src/main.py` — initialize QApplication, load Settings, start BridgeManager, create MainWindow, handle clean shutdown (stop bridge on exit)

**Checkpoint**: User Story 1 is fully functional — an admin can load an Excel, send WhatsApp reminders, and view/export results. This is the MVP.

---

## Phase 4: User Story 2 — Configurar Plantilla de Mensaje (Priority: P2)

**Goal**: The admin can customize the message template using variables, and the template is persisted for future sends.

**Independent Test**: Open Settings, modify the template to include custom text (e.g., clinic name), save, send a reminder, and verify the received WhatsApp message contains the customized text.

### Implementation for User Story 2

- [X] T024 [US2] Implement settings dialog in `src/ui/settings_dialog.py` — QDialog with: message template editor (QPlainTextEdit with monospace font), variable reference panel showing available {{variables}}, default country code input (QLineEdit with + prefix), bridge port input (QSpinBox), live preview button showing rendered message with sample data, save/cancel buttons; persist via SettingsStore

**Checkpoint**: User Story 2 is functional — the admin can customize the message template and it persists across sessions.

---

## Phase 5: User Story 3 — Consultar Historial de Envíos (Priority: P3)

**Goal**: The admin can view a history of past send sessions, stored locally as JSON files, and inspect details of any past session.

**Independent Test**: Perform two sends with different Excel files, close the app, reopen it, open the History tab, and verify both sessions appear with correct counts and details.

### Implementation for User Story 3

- [X] T025 [P] [US3] Implement history store in `src/services/history_store.py` — save SendSession to JSON file in platformdirs data directory (history/{timestamp}.json), list all past sessions (sorted by date desc), load a specific session by ID, delete old sessions
- [X] T026 [US3] Implement history view widget in `src/ui/history_view.py` — QWidget with: session list (QListWidget showing date, total/sent/failed counts), "View Details" button opening a read-only results table, "Delete" button to remove old sessions; integrate as a tab in MainWindow

**Checkpoint**: User Story 3 is functional — the admin can browse past send sessions and inspect their details.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and final packaging

- [X] T027 [P] Add error handling and user-friendly error messages across all services — translate technical errors to Spanish user-facing messages per FR requirements, show QMessageBox for critical errors
- [X] T028 [P] Add application icon and window title in `src/ui/main_window.py` — set window title "WhatsApp Notifier", add app icon, set minimum window size
- [X] T029 [P] Add status bar with WhatsApp connection indicator in `src/ui/main_window.py` — show 🔴 Disconnected / 🟢 Connected status, auto-refresh every 30s
- [X] T030 Create PyInstaller spec file for Windows packaging — bundle src/ as onefile windowed app, include bridge/ as data files, output WhatsAppNotifier.exe
- [X] T031 Create build script `scripts/build.sh` — run PyInstaller for Python side, run pkg for Node.js bridge, assemble dist/ folder with both executables
- [X] T032 Run quickstart.md validation — follow the quickstart guide step-by-step to verify all instructions work, fix any discrepancies

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2) — No dependencies on other stories
- **User Story 2 (Phase 4)**: Depends on Foundational (Phase 2) — Integrates with US1 (uses Settings model, template renderer)
- **User Story 3 (Phase 5)**: Depends on Foundational (Phase 2) — Integrates with US1 (uses SendSession model, results table)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational — No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational — Uses Settings model (T006) and template renderer (T015) from US1, but independently testable
- **User Story 3 (P3)**: Can start after Foundational — Uses SendSession model (T009) from Foundational, but independently testable

### Within Each User Story

- Models before services
- Services before UI
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T003, T004, T005)
- All Foundational tasks marked [P] can run in parallel (T006–T013 are all independent files)
- Within US1: T014 (excel_reader) and T015 (template_renderer) can run in parallel
- Within US3: T025 (history_store) can run in parallel with other US3 work
- Polish tasks T027, T028, T029 can run in parallel

---

## Parallel Example: Foundational Phase

```bash
# All foundational tasks are independent files — can be implemented in parallel:
Task: "Create Settings model in src/models/settings.py"
Task: "Create Appointment model in src/models/appointment.py"
Task: "Create SendResult model in src/models/send_result.py"
Task: "Create SendSession model in src/models/send_history.py"
Task: "Implement Excel column mapper in src/utils/excel_column_mapper.py"
Task: "Implement phone normalizer in src/services/phone_normalizer.py"
Task: "Implement settings store in src/services/settings_store.py"
Task: "Create Node.js Baileys bridge in bridge/whatsapp-bridge.js"
```

## Parallel Example: User Story 1

```bash
# These US1 tasks are independent files — can be implemented in parallel:
Task: "Implement Excel reader in src/services/excel_reader.py"
Task: "Implement template renderer in src/services/template_renderer.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T005)
2. Complete Phase 2: Foundational (T006–T013) — CRITICAL, blocks all stories
3. Complete Phase 3: User Story 1 (T014–T023)
4. **STOP and VALIDATE**: Test User Story 1 independently — load Excel, scan QR, send reminders, view results
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Polish & Package → Final release

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (core send flow + UI)
   - Developer B: User Story 2 (settings dialog)
   - Developer C: User Story 3 (history view)
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- The Baileys bridge (T013) is the most critical foundational task — it enables all WhatsApp communication
- The bridge runs as a subprocess managed by the Python app — no manual startup required by end users
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
