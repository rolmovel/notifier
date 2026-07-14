# Contract: Evolution API Endpoints

**Date**: 2026-07-13
**Feature**: 001-whatsapp-appointment-notifier

## Overview

Evolution API v2.x exposes a REST API for WhatsApp messaging. n8n workflows call these endpoints via HTTP Request nodes. All requests require the `apikey` header for authentication.

## Base URL

```
http://evolution-api:8080
```

(Internal Docker network URL; configurable via `EVOLUTION_API_URL` environment variable)

## Authentication

All requests must include the header:
```
apikey: <EVOLUTION_API_KEY>
```

The API key is configured via the `.env` file and passed to n8n as an environment variable or n8n credential.

---

## Endpoints Used

### 1. Create WhatsApp Instance

Creates a WhatsApp connection instance in Evolution API.

```
POST /instance/create
```

**Request Body**:
```json
{
  "instanceName": "clinic-notifier",
  "qrcode": true,
  "integration": "whatsapp"
}
```

**Response** (200 OK):
```json
{
  "instance": {
    "instanceName": "clinic-notifier",
    "status": "created"
  },
  "qrcode": {
    "code": "2@...base64...",
    "base64": "data:image/png;base64,..."
  }
}
```

**Usage**: Called by `scripts/setup-evolution.sh` during initial setup. The QR code is displayed for scanning with the WhatsApp mobile app.

---

### 2. Configure Webhook

Sets the webhook URL where Evolution API sends incoming message events.

```
POST /webhook/set/clinic-notifier
```

**Request Body**:
```json
{
  "url": "http://n8n:5678/webhook/receive-reply",
  "events": [
    "messages.upsert",
    "connection.update"
  ]
}
```

**Response** (200 OK):
```json
{
  "webhook": {
    "url": "http://n8n:5678/webhook/receive-reply",
    "events": ["messages.upsert", "connection.update"],
    "enabled": true
  }
}
```

**Usage**: Called by `scripts/setup-evolution.sh` after instance creation. The webhook URL points to n8n's Webhook node for the "Receive Patient Reply" workflow.

---

### 3. Send Text Message

Sends a WhatsApp text message to a phone number.

```
POST /message/sendText/clinic-notifier
```

**Request Body**:
```json
{
  "number": "+34612345678",
  "text": "Hola Juan,\n\nLe recordamos su cita...",
  "delay": 1200
}
```

**Parameters**:
- `number` (string, required): Destination phone number in international format
- `text` (string, required): Message text content
- `delay` (integer, optional): Delay in milliseconds before sending (default: 1200, to avoid rate limiting)

**Response** (200 OK):
```json
{
  "key": {
    "remoteJid": "34612345678@s.whatsapp.net",
    "fromMe": true,
    "id": "3EB0XXXXXXX"
  },
  "message": {
    "extendedTextMessage": {
      "text": "Hola Juan..."
    }
  },
  "messageTimestamp": "1720886400",
  "status": "PENDING"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid phone number or missing required fields
- `401 Unauthorized`: Invalid or missing API key
- `500 Internal Server Error`: Evolution API or WhatsApp connection error

**Usage**: Called by n8n's "Send Appointment Notifications" workflow via HTTP Request node for each valid appointment record.

---

### 4. Check Instance Connection Status

Verifies that the WhatsApp instance is connected and ready.

```
GET /instance/connectionState/clinic-notifier
```

**Response** (200 OK):
```json
{
  "instance": {
    "instanceName": "clinic-notifier",
    "state": "open"
  }
}
```

**States**: `open` (connected), `close` (disconnected), `connecting` (in progress)

**Usage**: Called by the health-check workflow and by `scripts/setup-evolution.sh` to verify readiness before sending notifications.

---

## Incoming Webhook Payload (Evolution API → n8n)

When a patient sends a WhatsApp reply, Evolution API sends a POST request to the configured webhook URL (n8n's Webhook node).

**Payload**:
```json
{
  "event": "messages.upsert",
  "instance": "clinic-notifier",
  "data": {
    "key": {
      "remoteJid": "34612345678@s.whatsapp.net",
      "fromMe": false,
      "id": "3EB0YYYYYYY"
    },
    "message": {
      "conversation": "A qué hora es mi cita?"
    },
    "messageTimestamp": 1720886500
    },
    "pushName": "Juan García"
  }
}
```

**Key fields extracted by n8n**:
- `data.key.remoteJid`: Extract phone number (strip `@s.whatsapp.net` suffix, add `+` prefix)
- `data.message.conversation`: The patient's message text
- `data.pushName`: The patient's WhatsApp display name
- `data.messageTimestamp`: Message timestamp (Unix epoch)

---

## Rate Limiting

- Evolution API recommends a minimum delay of 1200ms between messages to avoid WhatsApp rate limiting.
- The n8n workflow uses the HTTP Request node's "Batching" option with `Batch Interval: 1200` ms to enforce this.
- For batches exceeding 100 messages, the workflow processes in chunks of 50 with a 60-second pause between chunks.

## Error Handling

- HTTP 5xx errors: n8n workflow retries with exponential backoff (5s, 15s, 45s) — 3 attempts max.
- HTTP 4xx errors: Not retried (client error — invalid number, bad request). Logged as failed.
- Connection timeout (30s): Treated as a retryable error.
