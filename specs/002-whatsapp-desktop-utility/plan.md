# Implementation Plan: WhatsApp Desktop Utility

**Branch**: `003-whatsapp-desktop-utility` | **Date**: 2026-07-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-whatsapp-desktop-utility/spec.md`

## Summary

A lightweight desktop application that reads appointment data from Excel files and sends WhatsApp reminder messages via an embedded Baileys bridge (no Docker, no database, no n8n). The app replaces the entire Evolution API + PostgreSQL + Redis + Docker stack with a single standalone GUI utility. Users load an Excel file with columns (hora de inicio, duración, gabinete, nombre del paciente, tipo de cita, teléfono fijo, teléfono móvil), configure a message template, scan a QR code on first run, then send reminders. A results report shows sent/failed messages and can be exported. A local history log (JSON files) stores past send sessions without requiring a database.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: 
- `PySide6` (Qt6 GUI framework — cross-platform desktop UI)
- `openpyxl` (Excel .xlsx file reading)
- `httpx` (async HTTP client — calls local Baileys bridge on localhost)
- `pydantic` (data validation and models)
- `phonenumbers` (Google libphonenumber — phone normalization to E.164)
- `platformdirs` (cross-platform config directory resolution)

**Node.js Bridge Dependencies** (bundled, not installed by user):
- `baileys` (@whiskeysockets/baileys — WhatsApp Web protocol via WebSocket)
- `express` (minimal HTTP server for Python ↔ Node.js communication)

**Storage**: Local JSON files for history and settings (no external database); Baileys session state persisted to local JSON file

**Testing**: `pytest` with `pytest-qt` for GUI testing, `pytest-httpx` for HTTP mocking

**Target Platform**: Windows 10/11 (primary), macOS 12+, Ubuntu 22.04+ (secondary)

**Project Type**: Desktop GUI application with embedded Node.js bridge subprocess

**Performance Goals**: Process and send 100 appointments in < 5 minutes; UI remains responsive during sending (async operations via QThread)

**Constraints**: < 100 MB packaged binary (Python side); Node.js bridge compiled with `pkg` (~40-60 MB, may be downloaded on first run if total exceeds 100 MB); offline-capable for file loading and history viewing; requires network only for WhatsApp messaging

**Scale/Scope**: Single-user desktop app; typical batch size 10–200 appointments per session

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution file (`.specify/memory/constitution.md`) is currently a placeholder template with no defined principles or gates. **No violations possible** — all gates pass vacuously.

| Gate | Status | Notes |
|------|--------|-------|
| Principles defined | ✅ Pass | Constitution is a template placeholder; no principles to violate |
| Complexity justification | ✅ Pass | Single-project structure, no unnecessary complexity |
| Testing strategy | ✅ Pass | pytest + pytest-qt covers unit, integration, and GUI testing |

## Project Structure

### Documentation (this feature)

```text
specs/002-whatsapp-desktop-utility/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── whatsapp-bridge-contract.md
│   └── excel-schema-contract.md
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
├── main.py                      # Entry point — launches QApplication + bridge
├── models/
│   ├── appointment.py            # Appointment data model (Pydantic)
│   ├── send_result.py            # SendResult model
│   ├── send_history.py           # SendHistory model
│   └── settings.py               # Settings model (bridge port, template, country code)
├── services/
│   ├── excel_reader.py           # Read & validate .xlsx files
│   ├── phone_normalizer.py       # Normalize phones to E.164
│   ├── whatsapp_client.py        # Baileys bridge HTTP client (send, status, QR)
│   ├── bridge_manager.py         # Start/stop/monitor Node.js bridge subprocess
│   ├── template_renderer.py      # Render message template with variables
│   ├── history_store.py          # Local JSON-based history persistence
│   └── settings_store.py         # Local JSON-based settings persistence
├── ui/
│   ├── main_window.py            # Main window: file selection, send button, results table
│   ├── settings_dialog.py        # Settings dialog (template editor, country code)
│   ├── results_table.py          # Results table widget (sent/failed report)
│   ├── qr_dialog.py              # QR code display dialog (first-run WhatsApp pairing)
│   └── history_view.py           # History view widget
└── utils/
    └── excel_column_mapper.py    # Map Excel column names to expected fields

bridge/                          # Node.js Baileys bridge (bundled with app)
├── whatsapp-bridge.js           # Express server: /status, /send, /qr endpoints
├── package.json                 # Baileys + Express dependencies
└── auth/                       # Baileys session state (persisted JSON)

tests/
├── unit/
│   ├── test_phone_normalizer.py
│   ├── test_template_renderer.py
│   ├── test_excel_reader.py
│   ├── test_whatsapp_client.py
│   └── test_bridge_manager.py
├── integration/
│   └── test_send_flow.py
└── gui/
    └── test_main_window.py
```

**Structure Decision**: Single-project structure with a `bridge/` subdirectory for the Node.js Baileys bridge. The Python app manages the bridge as a subprocess — no external server required. The `src/` directory separates concerns into `models/`, `services/`, `ui/`, and `utils/`. Tests mirror the source structure under `tests/`.

## Complexity Tracking

> No constitution violations — section intentionally left empty.
