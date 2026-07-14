# Research: WhatsApp Desktop Utility

**Date**: 2026-07-14
**Feature**: 002-whatsapp-desktop-utility

## Research Tasks

### R-001: Python GUI Framework Selection for Cross-Platform Desktop App

**Decision**: Use **PySide6** (Qt6 for Python) as the GUI framework.

**Rationale**: The spec requires a desktop GUI application that works on Windows (primary) and ideally macOS/Linux. PySide6 is the official Qt binding for Python, maintained by The Qt Company, with LGPL licensing (suitable for distribution). It provides:
- Native-looking widgets on all platforms (Windows, macOS, Linux)
- Table widgets for the results report (QTableWidget)
- File dialog integration for Excel selection
- Threading support via QThread/QThreadPool to keep UI responsive during async API calls
- Mature ecosystem with extensive documentation

PySide6 was chosen over alternatives because it is the official Qt binding (vs PyQt6 which is GPL/commercial), has better long-term support, and Qt is the industry standard for cross-platform desktop Python apps.

**Alternatives considered**:
- **Tkinter** (stdlib) — too basic for a polished table-based UI; lacks modern styling and file dialog customization is limited.
- **PyQt6** — functionally identical to PySide6 but GPL-licensed, requiring a commercial license for closed-source distribution.
- **CustomTkinter** — a modernized Tkinter wrapper, but still limited in widget complexity for data tables.
- **Electron (JS/TS)** — would require a completely different tech stack (Node.js) and produces much larger binaries (>150 MB). The project is Python-centric.
- **Flet (Flutter for Python)** — promising but still maturing; fewer community resources and potential API instability.

---

### R-002: Excel File Reading Library

**Decision**: Use **openpyxl** for reading `.xlsx` files.

**Rationale**: openpyxl is the de facto standard Python library for Excel `.xlsx` file manipulation. It supports:
- Reading cell values with proper type detection (dates, times, strings, numbers)
- Header row detection
- Large file handling (read-only mode)
- No dependency on Microsoft Excel or COM automation (critical for cross-platform)

The spec requires reading columns: hora de inicio, duración, gabinete, nombre del paciente, tipo de cita, teléfono fijo, teléfono móvil. openpyxl handles all these data types natively, including Excel's datetime serial numbers for time values.

**Alternatives considered**:
- **pandas** (with openpyxl engine) — adds unnecessary overhead; pandas is designed for data analysis, not simple file reading. The app only needs to iterate rows.
- **xlrd** — only supports legacy `.xls` format, not `.xlsx`.
- **xlwings** — requires Excel to be installed (Windows/macOS only, not cross-platform headless).
- **pyexcel** — another option but less maintained than openpyxl.

---

### R-003: Phone Number Normalization to E.164

**Decision**: Use the **phonenumbers** library (Google's libphonenumber Python port).

**Rationale**: The spec requires normalizing phone numbers to E.164 format and validating them before sending. The phonenumbers library is the gold standard for this:
- Parses phone numbers from various formats (national, international, with/without +)
- Validates numbers against country-specific rules
- Formats to E.164 (`+34612345678`)
- Handles edge cases (leading zeros, spaces, dashes, country code prefixes)

The app will use a configurable default country code (+34 Spain by default) to parse national-format numbers. The library automatically detects if a number already has an international prefix.

**Alternatives considered**:
- **Manual regex normalization** — error-prone; doesn't handle country-specific validation rules (e.g., Spanish mobile numbers are 9 digits starting with 6/7).
- **WhatsApp's own phone validation** — relies on the API to reject invalid numbers, but we want client-side validation before sending for better UX.

---

### R-004: WhatsApp Messaging Engine — Baileys Embedded Bridge

**Decision**: Use **Baileys** (TypeScript/Node.js library) embedded as a small local HTTP bridge process, managed automatically by the Python desktop app.

**Rationale**: Evolution API (used in feature 001) is too heavy for a standalone desktop utility — it requires Docker, PostgreSQL, and Redis. The user explicitly wants maximum simplicity with no external servers. Baileys is the ideal replacement:

- **No browser required** — Baileys connects directly to WhatsApp Web via WebSocket, implementing the Noise/protobuf protocol. No Puppeteer, no Chromium.
- **No database required** — session state can be persisted to a local JSON file.
- **Lightweight** — ~50–150 MB memory footprint (just Node.js + WebSocket + auth state).
- **Actively maintained** — tracks WhatsApp Web v2.3000.x (current as of 2025).
- **Supports pairing code** — can authenticate with just a phone number (no QR scan needed), though QR is also supported.

**Architecture**: The Python app bundles a small Node.js script (`bridge/whatsapp-bridge.js`, ~100 lines) that:
1. Starts an Express HTTP server on `localhost:3001`
2. Connects to WhatsApp using Baileys
3. Exposes endpoints: `GET /status`, `POST /send`, `GET /qr`
4. The Python app starts this process on launch (or on first send) and stops it on exit

The Python app communicates with the bridge via `httpx` (localhost HTTP calls). This keeps the UI responsive (QThread + httpx async) while Baileys handles the WhatsApp protocol.

**Packaging**: Node.js runtime is bundled alongside the Python app. PyInstaller packages the Python side; the Node.js bridge script + `node_modules` are included as data files. Alternatively, `pkg` can compile the Node.js bridge into a single binary.

**Alternatives considered**:
- **Evolution API (external)** — rejected; requires Docker + PostgreSQL + Redis running separately. Too heavy for a desktop utility.
- **whatsapp-web.js** — rejected; requires Puppeteer/Chromium (~500 MB), defeating the purpose of a lightweight app.
- **PyWhatKit** — rejected; opens a browser and uses pyautogui screen-scraping. Not reliable for batch sending, no headless mode.
- **yowsup** — rejected; abandoned since 2021, protocol is 4+ years out of date.
- **WhatsApp Cloud API (Meta official)** — viable alternative but requires Meta Business verification and has per-message costs (~0.07€/msg in Spain). Can be offered as a future option.
- **Third-party services (Twilio, CallMeBot)** — rejected; recurring costs and external dependency.

---

### R-005: Local Storage for Settings and History (No Database)

**Decision**: Use **JSON files** stored in a user-config directory for both settings and send history.

**Rationale**: The spec explicitly requires no databases. JSON files are:
- Human-readable (easy debugging)
- Simple to read/write with Python's stdlib `json` module
- No external dependencies
- Portable across platforms

**Settings file** (`~/.notifier-desktop/settings.json`):
- WhatsApp bridge port (default: 3001)
- Default country code
- Message template text
- Last used Excel file path

**History files** (`~/.notifier-desktop/history/`):
- One JSON file per send session, named by timestamp (e.g., `2026-07-14T103000.json`)
- Each file contains: timestamp, total/sent/failed counts, and per-appointment results
- History view loads and lists these files

The app uses `platformdirs` library (or manual path resolution) to determine the correct config directory per OS:
- Windows: `%APPDATA%/notifier-desktop/`
- macOS: `~/Library/Application Support/notifier-desktop/`
- Linux: `~/.config/notifier-desktop/`

**Alternatives considered**:
- **SQLite** — technically a database; the user explicitly said "no bases de datos". While SQLite is embedded, we respect the user's intent.
- **CSV files for history** — less structured than JSON; harder to store nested result data.
- **YAML** — requires additional dependency (PyYAML); JSON is sufficient and in stdlib.

---

### R-006: Excel Column Name Mapping Strategy

**Decision**: Use a **fuzzy column name mapper** that accepts variations of expected column names.

**Rationale**: The spec's edge case requires handling Excel files with column names that may differ slightly from expected. The app will define a mapping of canonical field names to accepted variations:

| Canonical Field | Accepted Column Names |
|-----------------|----------------------|
| `start_time` | "hora de inicio", "hora inicio", "hora", "inicio", "start time", "start_time" |
| `duration` | "duración", "duracion", "duration", "duración (min)" |
| `gabinete` | "gabinete", "ganinete", "gab", "sala", "consultorio", "office" |
| `patient_name` | "nombre del paciente", "paciente", "nombre", "patient name", "patient_name" |
| `appointment_type` | "tipo de cita", "tipo cita", "tipo", "appointment type", "type" |
| `phone_landline` | "teléfono fijo", "telefono fijo", "tel fijo", "fijo", "landline", "phone_landline" |
| `phone_mobile` | "teléfono móvil", "telefono movil", "tel movil", "movil", "móvil", "mobile", "phone_mobile" |

The mapper normalizes column names (lowercase, strip accents, strip punctuation) before matching. If a required column cannot be found, the app shows a clear error listing which columns are missing and what names were found.

**Alternatives considered**:
- **Exact match only** — rejected; too fragile for real-world Excel files created by different staff members.
- **Column position (index) based** — rejected; column order may vary between files.
- **AI-based column detection** — overkill for a small utility; rule-based fuzzy matching is sufficient.

---

### R-007: Message Template Variable System

**Decision**: Use Python's **string.Template** with custom delimiters (`{{variable}}` style).

**Rationale**: The spec requires a configurable message template with variables like `{{patient_name}}`, `{{appointment_date}}`, `{{appointment_time}}`, `{{appointment_type}}`, `{{gabinete}}`. 

A custom template renderer will:
1. Parse the template for `{{variable}}` patterns
2. Replace each variable with the corresponding value from the appointment data
3. If a variable is not found in the data, leave it empty and log a warning
4. Return the rendered message string

This approach is simple, has no external dependencies, and is easy for non-technical users to understand.

**Alternatives considered**:
- **Jinja2** — powerful but overkill for simple variable substitution; adds dependency.
- **Python str.format()** — requires named placeholders but fails on missing keys; less forgiving than needed.
- **f-strings** — not suitable for user-defined templates (security and syntax issues).

---

### R-008: Async Sending Strategy for UI Responsiveness

**Decision**: Use **QThread with a worker object** pattern for the sending process.

**Rationale**: The app must send WhatsApp messages one-by-one (or in small batches) while keeping the UI responsive. The QThread pattern in PySide6:
- Runs the sending loop in a background thread
- Emits progress signals to update the UI (progress bar, live results table)
- Allows cancellation mid-process
- Prevents UI freezing during network calls

The worker object will:
1. Receive the list of valid appointments
2. Iterate through them, calling the Baileys bridge (`POST localhost:3001/send`) for each
3. Emit `progress(int current, int total)` signal after each send
4. Emit `result_ready(SendResult)` signal after each attempt
5. Emit `finished(list[SendResult])` signal when all sends complete

httpx async client runs inside the worker thread for efficient connection reuse to the local Baileys bridge.

**Alternatives considered**:
- **asyncio event loop in Qt** — complex integration; QThread is simpler and more idiomatic for Qt.
- **multiprocessing** — overkill; the bottleneck is network I/O, not CPU.
- **Synchronous with QApplication.processEvents()** — hacky and unreliable; can cause reentrancy issues.

---

### R-009: Packaging for Windows Distribution

**Decision**: Use **PyInstaller** (Python side) + **pkg** (Node.js bridge) to create a standalone Windows distribution.

**Rationale**: The app has two runtime components:
1. **Python GUI** (PySide6) — packaged with PyInstaller into a single `.exe` or folder
2. **Node.js Baileys bridge** — compiled with `pkg` into a single `whatsapp-bridge.exe`

PyInstaller:
- Bundles Python interpreter + all dependencies (PySide6, openpyxl, httpx, phonenumbers, pydantic)
- Handles Qt binaries automatically
- No Python installation required on the target machine

`pkg` (for the Node.js bridge):
- Compiles the Baileys bridge script + Node.js runtime into a single executable
- No Node.js installation required on the target machine
- Output: `whatsapp-bridge.exe` (~40-60 MB)

The Python app launches `whatsapp-bridge.exe` as a subprocess on startup (or on first send) and terminates it on exit.

For cross-platform distribution, both PyInstaller and pkg support macOS and Linux.

Target size: < 100 MB total (SC-005). PySide6 + Python ~60-80 MB, Node.js bridge ~40-60 MB. May exceed 100 MB slightly; if so, the bridge can be downloaded on first run instead of bundled.

**Alternatives considered**:
- **cx_Freeze** — less mature than PyInstaller for Qt apps.
- **Nuitka** — compiles to C, smaller binaries but slower build times and potential Qt compatibility issues.
- **Bundle Node.js runtime separately** — simpler but requires user to install Node.js.
- **Docker** — rejected; the whole point is to avoid Docker/n8n complexity.

---

### R-010: WhatsApp Engine Comparison — Why Baileys over Evolution API

**Decision**: Replace Evolution API with an embedded Baileys bridge for the desktop utility.

**Rationale**: The user asked whether Evolution API should be packaged in the app and whether a lighter library exists. Evolution API is a full server stack (Node.js + PostgreSQL + Redis) designed for multi-tenant server deployment — it cannot be reasonably bundled into a desktop app. Baileys is the underlying WhatsApp library that Evolution API itself uses internally, but without the server infrastructure.

**Comparison Table**:

| Feature | Evolution API | Baileys (embedded) | whatsapp-web.js | PyWhatKit | yowsup | WhatsApp Cloud API |
|---------|---------------|--------------------|-----------------|-----------|--------|--------------------|
| **Standalone?** | ❌ Docker+PG+Redis | ✅ Node.js script | ❌ Chromium | ⚠️ Browser | ✅ | ✅ HTTP |
| **Memory** | ~500 MB+ | ~50-150 MB | ~500 MB+ | Variable | Low | 0 (cloud) |
| **Browser required** | No | No | Yes (Puppeteer) | Yes | No | No |
| **Maintained** | ✅ | ✅ (WA v2.3000.x) | ✅ | ⚠️ Stagnant | ❌ Dead (2021) | ✅ |
| **Batch reliable** | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| **Cost** | Free | Free | Free | Free | Free | ~0.07€/msg |
| **Setup complexity** | High (Docker) | Low (script) | Medium | Low | — | Medium (Meta verification) |
| **Python-native** | ❌ | ❌ (bridge) | ❌ | ✅ | ✅ | ✅ (HTTP) |

**Baileys is the sweet spot**: lightweight enough for a desktop app, reliable for batch sending, actively maintained, and free. The bridge pattern (small Node.js HTTP server managed by Python) is a well-established architecture.

**Future option**: WhatsApp Cloud API can be added later as an alternative backend (just a different `WhatsAppClient` implementation) if the clinic wants official API reliability and is willing to pay per message.
