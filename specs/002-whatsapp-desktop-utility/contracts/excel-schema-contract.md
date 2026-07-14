# Contract: Excel File Schema

**Date**: 2026-07-14
**Feature**: 002-whatsapp-desktop-utility

## Overview

Defines the expected structure of the Excel (.xlsx) file that the desktop application reads. The app uses fuzzy column name matching to handle variations in header naming.

## File Format

- **Extension**: `.xlsx` (Excel 2007+)
- **Sheet**: The first worksheet in the workbook is read by default
- **Header Row**: Row 1 is assumed to contain column headers
- **Data Rows**: Rows 2+ contain appointment data

## Required Columns

| Canonical Field | Required | Accepted Header Names (examples) | Data Type | Example |
|-----------------|----------|-----------------------------------|-----------|---------|
| `start_time` | Yes | "hora de inicio", "hora inicio", "hora", "inicio", "start time" | datetime or string | "2026-07-15 10:30" or Excel datetime |
| `duration` | Yes | "duración", "duracion", "duration", "duración (min)" | integer or string | 30 or "30" |
| `gabinete` | No | "gabinete", "ganinete", "gab", "sala", "consultorio" | string | "Sala 3" |
| `patient_name` | Yes | "nombre del paciente", "paciente", "nombre", "patient name" | string | "Juan García" |
| `appointment_type` | Yes | "tipo de cita", "tipo cita", "tipo", "appointment type" | string | "Limpieza dental" |
| `phone_landline` | No* | "teléfono fijo", "telefono fijo", "tel fijo", "fijo", "landline" | string | "912345678" or "+34912345678" |
| `phone_mobile` | No* | "teléfono móvil", "telefono movil", "tel movil", "movil", "móvil", "mobile" | string | "612345678" or "+34612345678" |

\* At least one phone column (mobile or landline) MUST be present per row.

## Column Matching Rules

1. Header text is normalized: lowercase, strip accents (á→a, é→e, etc.), strip leading/trailing whitespace, strip punctuation
2. Normalized header is matched against the accepted names list
3. If a required column is not found after normalization, the app shows an error:
   ```
   Columnas faltantes: hora de inicio, nombre del paciente, tipo de cita
   Columnas encontradas: duración, gabinete, teléfono móvil
   ```
4. If multiple columns match the same canonical field, the first match is used

## Data Type Handling

### `start_time`
- If the cell is an Excel datetime → parsed directly
- If the cell is a number (Excel serial) → converted to datetime
- If the cell is a string → parsed with `datetime.fromisoformat()` or common formats:
  - `YYYY-MM-DD HH:MM`
  - `DD/MM/YYYY HH:MM`
  - `YYYY-MM-DD`
  - `DD/MM/YYYY`
- If parsing fails → row marked invalid with error "Invalid date/time format"

### `duration`
- If the cell is a number → used as integer minutes
- If the cell is a string → parsed as integer
- If parsing fails or value ≤ 0 → row marked invalid with error "Invalid duration"

### Phone numbers (`phone_landline`, `phone_mobile`)
- Read as string (openpyxl may return numbers for phone cells)
- Leading zeros are preserved when reading as string
- Normalized to E.164 format using the `phonenumbers` library with the configured default country code

### `patient_name`, `gabinete`, `appointment_type`
- Read as string, trimmed of whitespace
- Empty strings for required fields → row marked invalid

## Example Excel File

| hora de inicio | duración | gabinete | nombre del paciente | tipo de cita | teléfono fijo | teléfono móvil |
|----------------|----------|----------|----------------------|--------------|----------------|----------------|
| 2026-07-15 10:30 | 30 | Sala 3 | Juan García | Limpieza dental | 912345678 | 612345678 |
| 2026-07-15 11:00 | 45 | Sala 1 | María López | Revisión | | 623456789 |
| 2026-07-15 12:00 | 60 | Sala 2 | Carlos Ruiz | Empaste | 913456789 | |

In row 3, the mobile phone is empty, so the landline `913456789` will be used (normalized to `+34913456789`).

## Error Reporting

When the Excel file has structural issues, the app reports:

| Error Type | Message | Action |
|------------|---------|--------|
| File not found | "No se pudo abrir el archivo: {path}" | Block processing |
| Invalid format | "El archivo no es un Excel válido (.xlsx)" | Block processing |
| Empty file | "El archivo no contiene filas de datos" | Block processing |
| Missing required column | "Faltan columnas obligatorias: {list}. Columnas encontradas: {list}" | Block processing |
| Invalid row data | Per-row errors in the results table | Continue processing other rows |
