# Data Model: WhatsApp Desktop Utility

**Date**: 2026-07-14
**Feature**: 002-whatsapp-desktop-utility

## Overview

The data model defines the in-memory structures used by the desktop application. All models are Pydantic `BaseModel` subclasses for validation. No database is used — data flows from Excel → models → Baileys bridge (local HTTP) → results, with history persisted as JSON files.

## Entities

### 1. Appointment

Represents a single appointment row read from the Excel file.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `row_number` | `int` | Yes | Row number in the Excel file (1-indexed, excluding header) |
| `start_time` | `datetime` | Yes | Appointment start date and time |
| `duration_minutes` | `int` | Yes | Duration in minutes |
| `gabinete` | `str` | No | Office/cabinet name |
| `patient_name` | `str` | Yes | Patient's full name |
| `appointment_type` | `str` | Yes | Type of appointment (e.g., "Limpieza", "Revisión") |
| `phone_landline` | `str \| None` | No | Landline phone number (raw from Excel) |
| `phone_mobile` | `str \| None` | No | Mobile phone number (raw from Excel) |
| `phone_normalized` | `str \| None` | Computed | E.164-normalized phone (mobile preferred, fallback to landline) |
| `is_valid` | `bool` | Computed | Whether the row passed validation |
| `validation_errors` | `list[str]` | Computed | List of validation error messages (empty if valid) |

**Validation Rules**:
- `patient_name` MUST be non-empty
- At least one phone (`phone_mobile` or `phone_landline`) MUST be present
- `phone_normalized` is computed by preferring mobile over landline
- `phone_normalized` MUST match E.164 format (`^\+[1-9]\d{6,14}$`) after normalization
- `start_time` MUST be a valid datetime
- `duration_minutes` MUST be a positive integer

**Phone Selection Logic**:
1. If `phone_mobile` is present and normalizable → use it
2. Else if `phone_landline` is present and normalizable → use it
3. Else → mark row as invalid with error "No valid phone number found"

---

### 2. SendResult

Represents the outcome of attempting to send a WhatsApp message for one appointment.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `appointment` | `Appointment` | Yes | The original appointment data |
| `status` | `enum: "sent" \| "failed"` | Yes | Send outcome |
| `phone_used` | `str` | Yes | The phone number the message was sent to (E.164) |
| `message_sent` | `str` | Yes | The rendered message text that was sent |
| `sent_at` | `datetime \| None` | No | Timestamp of successful send (None if failed) |
| `error_reason` | `str \| None` | No | Error message if status is "failed" |
| `api_response` | `dict \| None` | No | Raw Baileys bridge response (for debugging) |

---

### 3. SendSession

Represents a complete sending session (one Excel file processed).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | `str` | Yes | UUID4 identifier |
| `started_at` | `datetime` | Yes | When the session started |
| `completed_at` | `datetime \| None` | No | When the session completed (None if in progress) |
| `source_file` | `str` | Yes | Path to the Excel file processed |
| `total_appointments` | `int` | Yes | Total rows in the Excel |
| `valid_appointments` | `int` | Yes | Rows that passed validation |
| `results` | `list[SendResult]` | Yes | One result per appointment (including invalid ones marked as failed) |

**Computed Properties**:
- `sent_count` → `len([r for r in results if r.status == "sent"])`
- `failed_count` → `len([r for r in results if r.status == "failed"])`
- `pending_count` → `total_appointments - len(results)` (during in-progress sessions)

---

### 4. Settings

Represents user-configurable application settings, persisted as JSON.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `bridge_port` | `int` | Yes | `3001` | Port for the local Baileys bridge HTTP server |
| `default_country_code` | `str` | Yes | `+34` | Default country code for phone normalization |
| `message_template` | `str` | Yes | *(see default below)* | Message template with `{{variable}}` placeholders |
| `last_file_path` | `str \| None` | No | `None` | Last used Excel file path (for convenience) |

**Default Message Template**:
```
Hola {{patient_name}},

Le recordamos su cita el {{appointment_date}} a las {{appointment_time}} para {{appointment_type}}.

Por favor, responda 'CONFIRMAR' para ratificar su asistencia o póngase en contacto si necesita reprogramar.

¡Gracias!
```

**Available Template Variables**:
| Variable | Source | Example |
|----------|--------|---------|
| `{{patient_name}}` | Appointment.patient_name | "Juan García" |
| `{{appointment_date}}` | Appointment.start_time (date part) | "2026-07-15" |
| `{{appointment_time}}` | Appointment.start_time (time part) | "10:30" |
| `{{appointment_type}}` | Appointment.appointment_type | "Limpieza dental" |
| `{{gabinete}}` | Appointment.gabinete | "Sala 3" |

---

## State Transitions

### SendSession Status Flow

```
[created] → [in_progress] → [completed]
                ↓
            [cancelled] (user cancels mid-send)
```

### SendResult Status Flow (per appointment)

```
[pending] → [sending] → [sent]     (success)
                 ↓
              [failed]   (API error, invalid phone, timeout)
```

Invalid appointments (failed validation) skip the `sending` state and go directly to `failed` with the validation error as `error_reason`.

---

## File-Based Persistence Schema

### Settings JSON (`settings.json`)

```json
{
  "bridge_port": 3001,
  "default_country_code": "+34",
  "message_template": "Hola {{patient_name}}, ...",
  "last_file_path": "/home/user/citas/citas_2026-07-14.xlsx"
}
```

### History JSON (`history/2026-07-14T103000.json`)

```json
{
  "session_id": "a1b2c3d4-...",
  "started_at": "2026-07-14T10:30:00",
  "completed_at": "2026-07-14T10:31:45",
  "source_file": "/home/user/citas/citas_2026-07-14.xlsx",
  "total_appointments": 50,
  "valid_appointments": 47,
  "results": [
    {
      "appointment": {
        "row_number": 1,
        "patient_name": "Juan García",
        "phone_normalized": "+34612345678",
        "start_time": "2026-07-15T10:30:00",
        "duration_minutes": 30,
        "gabinete": "Sala 3",
        "appointment_type": "Limpieza dental"
      },
      "status": "sent",
      "phone_used": "+34612345678",
      "message_sent": "Hola Juan García, ...",
      "sent_at": "2026-07-14T10:30:05",
      "error_reason": null
    }
  ]
}
```
