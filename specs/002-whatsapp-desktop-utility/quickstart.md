# Quickstart: WhatsApp Desktop Utility

**Date**: 2026-07-14
**Feature**: 002-whatsapp-desktop-utility

## Prerequisites

1. **Node.js 18+** installed on your machine (for the Baileys bridge — only needed for development; the packaged app bundles it)
2. **Excel file** (.xlsx) with appointment data (see [excel-schema-contract.md](./contracts/excel-schema-contract.md))
3. **Python 3.11+** installed (for development) OR the packaged `.exe` (for end users)

> **No external server required.** The app embeds a lightweight Node.js bridge (Baileys) that connects directly to WhatsApp. No Docker, no PostgreSQL, no Evolution API.

## Installation (Development)

```bash
# Clone the repository
git clone <repo-url>
cd notifier

# Create a Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js bridge dependencies
cd bridge && npm install && cd ..

# Run the application
python main.py
# or: python -m src
```

The app will automatically start the Baileys bridge subprocess on first launch.

## First Run Setup

1. **Launch the application** — the main window appears. The app automatically starts the Baileys bridge in the background.
2. **Connect WhatsApp** — on first run, the app detects no active WhatsApp session and shows a QR code dialog:
   - Open WhatsApp on your phone → Settings → Linked Devices → Link a Device
   - Scan the QR code displayed in the app
   - Wait a few seconds for the connection to establish
   - The session is saved locally — subsequent launches auto-connect without QR
3. **Open Settings** (gear icon or File → Settings) to configure:
   - **Default Country Code**: e.g., `+34` (Spain) — used for phone normalization
   - **Message Template**: customize the reminder text (see template variables below)
4. **Save settings**

> **Alternative pairing**: Instead of QR, you can use a phone number pairing code. Go to WhatsApp → Linked Devices → Link a Device → "Link with phone number" and enter the code shown in the app.

## Sending Appointment Reminders

1. **Click "Select Excel File"** — choose your `.xlsx` file with appointment data
2. **Preview** — the app shows the parsed appointments and any validation errors
3. **Click "Send Reminders"** — the app:
   - Checks WhatsApp connection status (via local bridge)
   - Sends WhatsApp messages one by one (with 1.2s delay between sends)
   - Shows live progress (progress bar + results updating in real-time)
4. **View Results** — when complete, the results table shows:
   - Patient name, phone, appointment date/time
   - Status: ✅ Sent / ❌ Failed
   - Error reason (if failed)
5. **Export Results** (optional) — click "Export to CSV" to save the report

## Checking Send History

1. Click the **History** tab
2. See a list of past send sessions with date, total/sent/failed counts
3. Click a session to view its full details

## Building a Standalone Executable

```bash
# Install PyInstaller
pip install pyinstaller

# Build Python side
pyinstaller --onefile --windowed --name "WhatsAppNotifier" main.py

# Build Node.js bridge (using pkg)
npx pkg bridge/whatsapp-bridge.js --targets node18-win-x64 --output dist/whatsapp-bridge.exe

# The final package contains:
#   dist/WhatsAppNotifier.exe   (Python GUI app)
#   dist/whatsapp-bridge.exe    (Node.js Baileys bridge)
#   dist/bridge/auth/           (session state, created on first run)
```

> **Note**: The Python app expects `whatsapp-bridge.exe` (or `whatsapp-bridge` on macOS/Linux) in the same directory. It automatically starts it on launch and stops it on exit.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "WhatsApp disconnected" | Click "Connect WhatsApp" and scan the QR code with your phone |
| "Bridge failed to start" | Ensure Node.js 18+ is installed (dev mode) or that `whatsapp-bridge.exe` is in the same directory (packaged mode) |
| "No valid phone number found" | Ensure the Excel has at least one phone column per row |
| "Missing required columns" | Check that the Excel headers match expected names (see [Excel Schema](./contracts/excel-schema-contract.md)) |
| Messages sent but not received | Verify the phone number is correct and has an active WhatsApp account |
| App freezes during sending | This shouldn't happen (sends run in background thread). If it does, report as a bug. |
| QR code expired | Click "Refresh QR" — Baileys generates a new QR code automatically |

## Default Message Template

```
Hola {{patient_name}},

Le recordamos su cita el {{appointment_date}} a las {{appointment_time}} para {{appointment_type}}.

Por favor, responda 'CONFIRMAR' para ratificar su asistencia o póngase en contacto si necesita reprogramar.

¡Gracias!
```

Customize in Settings to match your clinic's tone and language.
