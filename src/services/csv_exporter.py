"""CSV exporter — export send results to a CSV file.

The data columns are taken dynamically from the Excel headers stored in each
appointment's ``raw_data``. Fixed columns are appended: the verified send
status (delivered/pending/failed), message_id, sent_at, delivered_at and the
error reason.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from src.models.send_result import SendResult, SendStatus

logger = logging.getLogger(__name__)

# Map send status to CSV status string
_STATUS_TEXT = {
    SendStatus.DELIVERED: "delivered",
    SendStatus.SENDING: "pending",
    SendStatus.PENDING: "pending",
    SendStatus.FAILED: "failed",
}

# Fixed columns appended after the dynamic Excel columns
_FIXED_COLUMNS = ["status", "message_id", "sent_at", "delivered_at", "error_reason"]


def export_results_to_csv(results: list[SendResult], file_path: str | Path) -> None:
    """Export a list of send results to a CSV file.

    The CSV columns are the Excel headers (taken from the first result's
    appointment ``raw_data``) plus the fixed delivery-status columns.

    Args:
        results: List of SendResult objects.
        file_path: Destination file path.

    Raises:
        OSError: If the file cannot be written.
    """
    path = Path(file_path)

    # Determine the data columns from the first result, if any.
    data_headers: list[str] = []
    if results:
        first_appt = results[0].appointment
        data_headers = list(first_appt.raw_data.keys()) if first_appt else []

    csv_headers = data_headers + _FIXED_COLUMNS

    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(csv_headers)

            for result in results:
                appointment = result.appointment
                status_text = _STATUS_TEXT.get(result.status, "unknown")
                sent_at_str = result.sent_at.isoformat() if result.sent_at else ""
                delivered_at_str = result.delivered_at.isoformat() if result.delivered_at else ""

                data_row = [appointment.get(h) for h in data_headers] if appointment else []
                fixed_row = [
                    status_text,
                    result.message_id or "",
                    sent_at_str,
                    delivered_at_str,
                    result.error_reason or "",
                ]
                writer.writerow(data_row + fixed_row)

        logger.info("Exported %d results to %s", len(results), path)
    except OSError as exc:
        logger.error("Failed to export CSV: %s", exc)
        raise