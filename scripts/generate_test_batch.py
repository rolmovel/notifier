"""Generate a test Excel file with 100 rows, all messages to the allowed test phones.

Only 629071739 and 629335570 are used (per project policy). Columns follow
specs/002-whatsapp-desktop-utility/contracts/excel-schema-contract.md.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import Workbook

PHONES = ["629071739", "629335570"]
APPOINTMENT_TYPES = ["Limpieza", "Revisión", "Empaste", "Extracción", "Ortodoncia"]
GABINETES = ["Sala 1", "Sala 2", "Sala 3"]
ROWS = 100
BASE_DAY = datetime(2026, 7, 20, 9, 0)  # Monday 09:00

OUT = Path(__file__).resolve().parent.parent / "test-data" / "lote-100-whatsapp.xlsx"

HEADERS = [
    "hora de inicio",
    "duración",
    "gabinete",
    "nombre del paciente",
    "tipo de cita",
    "teléfono fijo",
    "teléfono móvil",
]


def main() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Citas"
    ws.append(HEADERS)

    for i in range(ROWS):
        start = BASE_DAY + timedelta(minutes=30 * i)
        phone = PHONES[i % len(PHONES)]
        ws.append([
            start,                       # hora de inicio (Excel datetime)
            15 + 15 * (i % 4),           # duración: 15/30/45/60
            GABINETES[i % len(GABINETES)],
            f"Paciente {i + 1:03d}",
            APPOINTMENT_TYPES[i % len(APPOINTMENT_TYPES)],
            None,                        # teléfono fijo (vacío)
            phone,                       # teléfono móvil (autorizado)
        ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"OK: {OUT} ({ROWS} filas)")


if __name__ == "__main__":
    main()