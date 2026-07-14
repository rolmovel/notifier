# Contract: Appointment File Schema

**Date**: 2026-07-13
**Feature**: 001-whatsapp-appointment-notifier

## Overview

Defines the expected format for appointment files uploaded by clinic staff. The system supports CSV and Excel (XLSX) formats.

## Supported Formats

- **CSV**: UTF-8 encoded, comma-separated, with header row
- **XLSX**: Microsoft Excel format, first sheet, with header row

## Column Specification

| Column Name | Type | Required | Format | Example |
|-------------|------|----------|--------|---------|
| patient_name | String | Yes | Free text, max 100 chars | `Juan García Pérez` |
| patient_phone | String | Yes | International format with `+` prefix | `+34612345678` |
| appointment_date | String | Yes | ISO 8601 date: `YYYY-MM-DD` | `2026-07-20` |
| appointment_time | String | Yes | 24h format: `HH:MM` | `14:30` |
| appointment_type | String | Yes | Free text, max 200 chars | `Consulta general` |

## CSV Example

```csv
patient_name,patient_phone,appointment_date,appointment_time,appointment_type
Juan García Pérez,+34612345678,2026-07-20,14:30,Consulta general
María López Fernández,+34698765432,2026-07-20,15:00,Limpieza dental
Carlos Ruiz Gómez,+34655554321,2026-07-21,10:00,Revisión ortodoncia
Ana Martínez Soto,+34644441234,2026-07-21,11:30,Extracción muela
Pedro Sánchez Lima,+34633335678,2026-07-22,09:00,Consulta general
```

## XLSX Example

| patient_name | patient_phone | appointment_date | appointment_time | appointment_type |
|---|---|---|---|---|
| Juan García Pérez | +34612345678 | 2026-07-20 | 14:30 | Consulta general |
| María López Fernández | +34698765432 | 2026-07-20 | 15:00 | Limpieza dental |

## Validation Rules

1. **Header row**: Must be present with exact column names (case-insensitive). Extra columns are ignored.
2. **patient_name**: Must not be empty. Leading/trailing whitespace is trimmed.
3. **patient_phone**: Must match regex `^\+[1-9]\d{6,14}$`. Numbers without `+` prefix are rejected (not auto-corrected to avoid wrong-country-code assumptions).
4. **appointment_date**: Must be a valid date in `YYYY-MM-DD` format. Must be today or in the future (past dates generate a warning but are still processed).
5. **appointment_time**: Must match `^([01]\d|2[0-3]):([0-5]\d)$`.
6. **appointment_type**: Must not be empty.
7. **Empty rows**: Skipped silently (do not count as invalid records).
8. **Maximum file size**: 10MB. Files exceeding this are rejected.
9. **Maximum records**: 1000 per file. Files with more records are rejected with a message to split the batch.

## Invalid Record Handling

Records that fail validation are:
- Excluded from the notification sending process
- Included in the error report with the specific validation failure reason
- Do not prevent valid records in the same file from being processed

**Example error report entry**:
```json
{
  "rowNumber": 5,
  "patientName": "Ana Martínez",
  "phoneNumber": "644441234",
  "errors": [
    "patient_phone: Invalid format. Expected international format with + prefix (e.g., +34612345678)"
  ]
}
```

## Phone Number Normalization

The system does **not** auto-correct phone numbers. Phone numbers must be provided in full international format with the country code. This is a deliberate decision to prevent messages being sent to wrong numbers due to incorrect country code assumptions.

If the clinic consistently provides numbers without country code, a default country code can be configured via the `DEFAULT_COUNTRY_CODE` environment variable (e.g., `+34` for Spain). When set, numbers without `+` prefix will be prefixed with this code.
