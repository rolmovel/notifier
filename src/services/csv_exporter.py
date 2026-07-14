"""CSV exporter — export send results to a CSV file."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from src.models.send_result import SendResult, SendStatus

logger = logging.getLogger(__name__)

# CSV column headers
CSV_HEADERS = [
    "patient_name",
    "phone",
    "appointment_date",
    "appointment_time",
    "status",
    "error_reason",
    "sent_at",
]


def export_results_to_csv(results: list[SendResult], file_path: str | Path) -> None:
    """Export a list of send results to a CSV file.

    Args:
        results: List of SendResult objects.
        file_path: Destination file path.

    Raises:
        OSError: If the file cannot be written.
    """
    path = Path(file_path)

    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)

            for result in results:
                appointment = result.appointment
                status_text = "sent" if result.status == SendStatus.SENT else "failed"
                sent_at_str = result.sent_at.isoformat() if result.sent_at else ""

                writer.writerow([
                    appointment.patient_name,
                    result.phone_used,
                    appointment.start_time.strftime("%Y-%m-%d"),
                    appointment.start_time.strftime("%H:%M"),
                    status_text,
                    result.error_reason or "",
                    sent_at_str,
                ])

        logger.info("Exported %d results to %s", len(results), path)
    except OSError as exc:
        logger.error("Failed to export CSV: %s", exc)
        raise
