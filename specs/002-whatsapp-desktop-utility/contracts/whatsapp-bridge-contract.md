# Contract: Baileys Bridge (Local HTTP)

**Date**: 2026-07-14
**Feature**: 002-whatsapp-desktop-utility

## Overview

The desktop application communicates with a **local Node.js HTTP bridge** (`bridge/whatsapp-bridge.js`) that wraps the Baileys library (`@whiskeysockets/baileys`). The bridge runs as a subprocess on `localhost:{port}` and exposes a minimal REST API. This contract defines the exact endpoints, request/response formats, and error handling used by the `WhatsAppClient` service.

## Architecture

```
┌─────────────────────┐     HTTP (localhost)     ┌──────────────────────┐
│  Python App (Qt6)   │ ────────────────────────── │  Node.js Bridge      │
│  whatsapp_client.py │  GET /status              │  (whatsapp-bridge.js) │
│  bridge_manager.py  │  POST /send               │  Baileys @whiskeysock │
│                     │  GET /qr                  │  ets/baileys          │
│                     │  POST /pair               │                       │
└─────────────────────┘                           └──────────┬───────────┘
                                                            │ WebSocket
                                                            ▼
                                                   ┌──────────────────┐
                                                   │  WhatsApp Servers  │
                                                   └──────────────────┘
```

## Base URL

Configurable via Settings (`bridge_port`). Default: `http://localhost:3001`

## Authentication

No API key required — the bridge binds to `127.0.0.1` only (no external access). Baileys session state is persisted to `bridge/auth/` as JSON files (auth keys, device pairing).

---

## Endpoints

### 1. Check Connection Status

Verifies that the WhatsApp connection is established and ready to send messages.

```
GET /status
```

**Response** (200 OK):
```json
{
  "connected": true,
  "state": "open",
  "phone": "+34612345678"
}
```

**States**:
| State | Meaning | Action |
|-------|---------|--------|
| `open` | Connected and ready | Proceed with sending |
| `close` | Disconnected | Show QR dialog: "Please scan the QR code to connect." |
| `connecting` | In progress (first-run pairing) | Show: "Connecting to WhatsApp, please wait..." |

**Error Responses**:
- `503 Service Unavailable` — Bridge is starting up or Baileys not initialized yet
- `500 Internal Server Error` — Bridge process error

**Usage**: Called before sending any messages (FR-015). If the state is not `open`, the app blocks sending and shows the QR dialog.

---

### 2. Get QR Code (First-Run Pairing)

Retrieves the QR code for WhatsApp Web pairing. Called when `/status` returns `close` state.

```
GET /qr
```

**Response** (200 OK):
```json
{
  "qr_code": "2@/B1yX...",
  "expires_in": 60
}
```

**Response Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `qr_code` | string | Base64-encoded QR string (render as QR image in UI) |
| `expires_in` | int | Seconds until QR expires (Baileys default: ~60s) |

**Error Responses**:
| HTTP Status | Meaning | App Behavior |
|-------------|---------|--------------|
| `409 Conflict` | Already connected (`state: open`) | Skip QR, proceed to send |
| `503 Service Unavailable` | QR not yet available (bridge still connecting) | Retry after 2 seconds |

**Usage**: Called when the user clicks "Connect WhatsApp" or when the app detects `state: close`. The QR string is rendered as an image in `QrDialog`. After the user scans it with their phone, the bridge automatically connects and persists the session — subsequent launches skip the QR step.

---

### 3. Pair with Phone Number (Alternative to QR)

Alternative pairing method using a phone number + pairing code (no QR scan needed). Useful for headless setups.

```
POST /pair
```

**Request Body**:
```json
{
  "phone": "+34612345678"
}
```

**Response** (200 OK):
```json
{
  "pairing_code": "ABCD-1234",
  "expires_in": 90
}
```

**Usage**: The app sends the phone number, receives a pairing code, and displays it to the user. The user enters the code in WhatsApp → Settings → Linked Devices → Link a Device → "Link with phone number".

---

### 4. Send Text Message

Sends a WhatsApp text message to a phone number.

```
POST /send
```

**Request Body**:
```json
{
  "number": "+34612345678",
  "text": "Hola Juan García,\n\nLe recordamos su cita..."
}
```

**Body Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `number` | string | Yes | Destination phone number in E.164 format |
| `text` | string | Yes | Message text content (rendered template) |

**Response** (200 OK):
```json
{
  "success": true,
  "message_id": "3EB0XXXXXXX",
  "timestamp": 1720886400
}
```

**Error Responses**:
| HTTP Status | Meaning | App Behavior |
|-------------|---------|--------------|
| `400 Bad Request` | Invalid phone number or missing fields | Mark as failed: "Invalid phone number" |
| `409 Conflict` | Not connected (WhatsApp disconnected) | Stop all sends: "WhatsApp disconnected. Please reconnect." |
| `429 Too Many Requests` | Rate limited by WhatsApp | Retry with exponential backoff (max 3 retries) |
| `500 Internal Server Error` | Baileys or WhatsApp error | Mark as failed with error message |
| `502/503/504` | Bridge unavailable | Retry with backoff (max 3 retries) |

**Usage**: Called for each valid appointment during the send loop. Messages are sent sequentially with a client-side delay (default: 1200ms) to avoid WhatsApp rate limiting.

---

## Bridge Lifecycle (Managed by `BridgeManager`)

The Python app manages the Node.js bridge subprocess:

1. **Start**: `BridgeManager.start()` spawns `node bridge/whatsapp-bridge.js --port {port}` as a subprocess
2. **Health check**: Poll `GET /status` every 1s until it responds (max 10s timeout)
3. **QR pairing** (first run only): If `state: close`, fetch QR → display in `QrDialog` → user scans → bridge auto-connects
4. **Ready**: `state: open` → app proceeds with sending
5. **Stop**: `BridgeManager.stop()` sends SIGTERM to the subprocess on app exit

**Session Persistence**: Baileys stores auth keys in `bridge/auth/`. After the first QR scan, the session is persisted. Subsequent app launches auto-connect without QR (unless the user logs out from their phone).

---

## Retry Strategy

For transient errors (429, 502, 503, 504, network timeouts):
1. Wait 5 seconds (initial backoff)
2. Retry up to 3 times with exponential backoff (5s, 10s, 20s)
3. If all retries fail, mark the appointment as failed with error "Max retries exceeded: {last_error}"

For permanent errors (400, 409):
- No retry; mark as failed immediately with the specific error message

---

## Rate Limiting

The app sends messages sequentially (not in parallel) with a configurable delay between sends (default: 1200ms). This prevents WhatsApp from flagging the number as spam.

**Client-side delay**: A `asyncio.sleep(1.2)` between each `/send` call prevents overwhelming the bridge and WhatsApp servers.

---

## Bridge Source Code Reference

The bridge is a minimal Express server (~100 lines). Key structure:

```javascript
// bridge/whatsapp-bridge.js (conceptual)
const express = require('express');
const { default: makeWASocket, useMultiFileAuthState } = require('@whiskeysockets/baileys');

const app = express();
app.use(express.json());

// Baileys socket with persisted auth state
const { state, saveCreds } = await useMultiFileAuthState('./auth');
const sock = makeWASocket({ auth: state });
sock.ev.on('creds.update', saveCreds);

// GET /status — check connection
// GET /qr — get current QR code
// POST /pair — request pairing code
// POST /send — send text message

app.listen(port, '127.0.0.1');
```
