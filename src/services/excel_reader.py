"""Excel reader — read .xlsx files into schema-agnostic Appointment rows.

The reader is decoupled from the Excel schema: every row is stored verbatim as
a mapping of original header -> string cell value (``raw_data``). The only
piece of structure the reader needs is the name of the header that holds the
destination phone (``phone_header``), which the user configures in Settings.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from src.models.appointment import Appointment
from src.utils.excel_column_mapper import build_header_index, has_header_row

logger = logging.getLogger(__name__)


class ExcelReadError(Exception):
    """Raised when the Excel file cannot be read or is invalid."""

    def __init__(self, message: str, found_columns: list[str] | None = None,
                 missing_columns: list[str] | None = None) -> None:
        super().__init__(message)
        self.found_columns = found_columns or []
        self.missing_columns = missing_columns or []


def _parse_cell_as_str(value: Any) -> str:
    """Convert a cell value to a cleaned string."""
    if value is None:
        return ""
    # Preserve datetime cells as ISO-ish strings so templates can render them.
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat(sep=" ")
        except Exception:
            pass
    return str(value).strip()


def read_excel_headers(file_path: str | Path) -> list[str]:
    """Read only the header row (row 1) of an Excel file.

    Args:
        file_path: Path to the .xlsx file.

    Returns:
        List of header strings as they appear in the file (empty strings for
        blank header cells).

    Raises:
        ExcelReadError: If the file cannot be read or has no header row.
    """
    path = Path(file_path)

    if not path.exists():
        raise ExcelReadError(f"No se pudo abrir el archivo: {path}")

    if path.suffix.lower() != ".xlsx":
        raise ExcelReadError("El archivo no es un Excel válido (.xlsx)")

    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise ExcelReadError(f"No se pudo abrir el archivo: {path}") from exc

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        raise ExcelReadError("El archivo no contiene filas")

    return [str(h) if h is not None else "" for h in rows[0]]


def _row_to_raw_data(headers: list[str], row: tuple) -> dict[str, str]:
    """Build a mapping of original header name -> string cell value for a row."""
    raw: dict[str, str] = {}
    for idx, header in enumerate(headers):
        if not header:
            continue
        value = row[idx] if idx < len(row) else None
        raw[header] = _parse_cell_as_str(value)
    return raw


def read_excel(
    file_path: str | Path,
    phone_header: str = "",
    default_country_code: str = "+34",
) -> list[Appointment]:
    """Read an Excel file and return a list of schema-agnostic Appointment rows.

    Args:
        file_path: Path to the .xlsx file.
        phone_header: Name of the header (as it appears in the Excel) that holds
            the destination phone number. May be empty; in that case rows will
            be flagged as invalid (no phone mapped).
        default_country_code: Country code for phone normalization.

    Returns:
        List of Appointment objects.

    Raises:
        ExcelReadError: If the file cannot be read or has no header row.
    """
    path = Path(file_path)

    if not path.exists():
        raise ExcelReadError(f"No se pudo abrir el archivo: {path}")

    if path.suffix.lower() != ".xlsx":
        raise ExcelReadError("El archivo no es un Excel válido (.xlsx)")

    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise ExcelReadError(f"No se pudo abrir el archivo: {path}") from exc

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows or len(rows) < 2:
        raise ExcelReadError("El archivo no contiene filas de datos")

    # First row = headers
    headers = [str(h) if h is not None else "" for h in rows[0]]

    if not has_header_row(headers):
        found_names = [h for h in headers if h.strip()]
        raise ExcelReadError(
            "El archivo no tiene una fila de cabecera con nombres de columna. "
            f"Columnas encontradas: {', '.join(found_names)}",
            found_columns=found_names,
            missing_columns=[],
        )

    # Sanity check: warn (not fail) if the mapped phone header is not present.
    build_header_index(headers)  # available for future lookups if needed
    if phone_header:
        present = any(
            str(h).strip().lower() == phone_header.strip().lower()
            for h in headers
        )
        if not present:
            logger.warning(
                "La cabecera de teléfono '%s' no se encuentra en el Excel. "
                "Las filas se marcarán como inválidas.",
                phone_header,
            )

    appointments: list[Appointment] = []

    for row_idx, row in enumerate(rows[1:], start=2):
        # Skip completely empty rows
        if all(cell is None or str(cell).strip() == "" for cell in row):
            continue

        raw_data = _row_to_raw_data(headers, row)

        appointment = Appointment(
            row_number=row_idx - 1,  # 1-indexed excluding header
            raw_data=raw_data,
            phone_header=phone_header,
            country_code=default_country_code,
        )
        appointments.append(appointment)

    return appointments
