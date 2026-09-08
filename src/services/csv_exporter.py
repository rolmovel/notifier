"""CSV exporter — export send results to a CSV file.

The data columns are taken dynamically from the Excel headers stored in each
appointment's ``raw_data``. Two fixed columns are appended: the send status
and the error reason.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from src.models.send_result import SendResult, SendStatus

logger = logging.getLogger(__name__)


def export_results_to_csv(results: list[SendResult], file_path: str | Path) -> None:
    """Export a list of send results to a CSV file.

    The CSV columns are the Excel headers (taken from the first result's
    appointment ``raw_data``) plus ``status`` and ``error_reason``.

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
        data_headers = list(results[0].appointment.raw_data.keys())

    csv_headers = data_headers + ["status", "error_reason"]

    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(csv_headers)

            for result in results:
                appointment = result.appointment
                status_text = "sent" if result.status == SendStatus.SENT else "failed"

                row = [appointment.get(h) for h in data_headers]
                row.append(status_text)
                row.append(result.error_reason or "")
                writer.writerow(row)

        logger.info("Exported %d results to %s", len(results), path)
    except OSError as exc:
        logger.error("Failed to export CSV: %s", exc)
        raise
