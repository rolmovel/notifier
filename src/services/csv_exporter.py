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
    "message_id",
    "sent_at",
    "delivered_at",
    "error_reason",
]

# Map send status to CSV status string
_STATUS_TEXT = {
    SendStatus.DELIVERED: "delivered",
    SendStatus.SENDING: "pending",
    SendStatus.PENDING: "pending",
    SendStatus.FAILED: "failed",
}


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
                status_text = _STATUS_TEXT.get(result.status, "unknown")
                sent_at_str = result.sent_at.isoformat() if result.sent_at else ""
                delivered_at_str = result.delivered_at.isoformat() if result.delivered_at else ""

                if appointment is None:
                    patient_name = ""
                    date_str = ""
                    time_str = ""
                else:
                    patient_name = appointment.patient_name
                    date_str = appointment.start_time.strftime("%Y-%m-%d")
                    time_str = appointment.start_time.strftime("%H:%M")

                writer.writerow([
                    patient_name,
                    result.phone_used,
                    date_str,
                    time_str,
                    status_text,
                    result.message_id or "",
                    sent_at_str,
                    delivered_at_str,
                    result.error_reason or "",
                ])

        logger.info("Exported %d results to %s", len(results), path)
    except OSError as exc:
        logger.error("Failed to export CSV: %s", exc)
        raise