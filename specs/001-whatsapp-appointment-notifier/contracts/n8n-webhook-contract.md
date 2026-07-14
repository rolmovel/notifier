# Contract: n8n Webhook Endpoints

**Date**: 2026-07-13
**Feature**: 001-whatsapp-appointment-notifier

## Overview

n8n exposes webhook endpoints that serve as entry points for workflows. These endpoints receive requests from external systems (clinic staff, Evolution API) and trigger n8n workflows.

## Base URL

```
http://n8n:5678/webhook/
```

(Internal Docker network URL; externally accessible via `http://<host>:5678/webhook/`)

---

## Endpoints

### 1. Upload Appointment File

Receives an appointment file upload from clinic staff and triggers the notification sending workflow.

```
POST /webhook/upload-appointments
```

**Content-Type**: `multipart/form-data`

**Request Body**:
- `file`: The appointment file (CSV or XLSX binary data)
- `batchId` (optional): Custom batch identifier; auto-generated if not provided

**Authentication**: Header auth (configurable API key via n8n credentials)

**Response** (200 OK):
```json
{
  "batchId": "550e8400-e29b-41d4-a716-446655440000",
  "totalRecords": 50,
  "validRecords": 48,
  "invalidRecords": 2,
  "status": "processing",
  "message": "File received and validated. Sending 48 notifications."
}
```

**Response** (400 Bad Request):
```json
{
  "error": "INVALID_FILE_FORMAT",
  "message": "File format not recognized. Expected CSV or XLSX.",
  "expectedFormats": [".csv", ".xlsx"]
}
```

**Usage**: Clinic staff (or an external system) sends a POST request with the appointment file. The workflow processes the file asynchronously and returns an immediate acknowledgment with the batch ID for tracking.

---

### 2. Receive Patient Reply (Evolution API Webhook)

Receives incoming WhatsApp message webhooks from Evolution API when a patient replies.

```
POST /webhook/receive-reply
```

**Content-Type**: `application/json`

**Request Body**: (See Evolution API contract for full payload structure)

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
```

**Authentication**: None (Evolution API webhooks do not include authentication by default; n8n webhook IP whitelist can be configured)

**Response**: `200 OK` (empty body — acknowledgment to Evolution API)

**Processing**: The workflow processes the message through guardrails and sends a bot response (or escalates) asynchronously. The webhook returns immediately to avoid Evolution API webhook timeout.

---

### 3. Get Notification Results

Retrieves the results of a notification batch.

```
GET /webhook/notification-results/:batchId
```

**Path Parameters**:
- `batchId`: The batch identifier returned from the upload endpoint

**Authentication**: Header auth (configurable API key)

**Response** (200 OK):
```json
{
  "batchId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "summary": {
    "totalAppointments": 50,
    "sent": 46,
    "failed": 2,
    "pending": 2
  },
  "failedRecords": [
    {
      "patientName": "María López",
      "phoneNumber": "+34611111111",
      "errorReason": "Invalid WhatsApp number",
      "retryCount": 3
    },
    {
      "patientName": "Carlos Ruiz",
      "phoneNumber": "+34622222222",
      "errorReason": "Evolution API timeout",
      "retryCount": 3
    }
  ]
}
```

**Response** (404 Not Found):
```json
{
  "error": "BATCH_NOT_FOUND",
  "message": "No notification batch found with ID: invalid-uuid"
}
```

**Usage**: Clinic staff queries the status of a notification batch using the batch ID from the upload response.

---

### 4. Bot Configuration Status

Retrieves the current bot configuration (enabled/disabled, business hours, etc.).

```
GET /webhook/bot-status
```

**Authentication**: Header auth (configurable API key)

**Response** (200 OK):
```json
{
  "enabled": true,
  "language": "es",
  "businessHours": {
    "start": "09:00",
    "end": "18:00",
    "timezone": "Europe/Madrid"
  },
  "allowedTopics": [
    "appointment_time",
    "appointment_date",
    "appointment_type",
    "clinic_location"
  ],
  "escalationRules": {
    "medicalTerms": true,
    "rescheduleRequest": true,
    "lowConfidenceThreshold": 0.7
  }
}
```

**Usage**: Allows clinic staff to check whether the bot is active and what its current configuration is.

---

## Webhook URL Configuration

n8n generates two webhook URL variants:
- **Test URL**: `http://n8n:5678/webhook-test/...` — active during workflow development/testing
- **Production URL**: `http://n8n:5678/webhook/...` — active when workflow is published/activated

Evolution API's webhook configuration must point to the **Production URL** for the "Receive Patient Reply" workflow.

## Security Considerations

- The upload and results endpoints should be protected with header authentication (API key).
- The receive-reply endpoint is called by Evolution API (internal Docker network); IP whitelist can restrict access to the Evolution API container's IP.
- All webhook payloads are logged in n8n execution history for audit purposes (FR-017).
- The maximum webhook payload size is 16MB (n8n default; configurable via `N8N_PAYLOAD_SIZE_MAX`).
