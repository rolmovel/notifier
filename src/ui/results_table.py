"""Results table widget — displays send results in a QTableWidget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)

from src.models.send_result import SendResult, SendStatus


class ResultsTable(QTableWidget):
    """Table widget showing send results with real-time updates.

    Rows are keyed by the appointment row number (falls back to message_id)
    so an in-flight result can be updated in place when the delivery tracker
    resolves it, without duplicating rows.
    """

    HEADERS = [
        "Paciente",
        "Teléfono",
        "Fecha Cita",
        "Hora Cita",
        "Estado",
        "Error",
    ]

    # Status → (label, color)
    STATUS_DISPLAY = {
        SendStatus.DELIVERED: ("✅ Entregado", Qt.GlobalColor.darkGreen),
        SendStatus.SENDING: ("⏳ Pendiente", Qt.GlobalColor.darkYellow),
        SendStatus.PENDING: ("⏳ Pendiente", Qt.GlobalColor.darkYellow),
        SendStatus.FAILED: ("❌ Fallido", Qt.GlobalColor.red),
    }

    def __init__(self, parent=None) -> None:
        super().__init__(0, len(self.HEADERS), parent)
        self._setup_ui()
        self._row_keys: dict[tuple, int] = {}  # key -> row index

    def _setup_ui(self) -> None:
        """Initialize the table UI."""
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)

        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)

    def _key_for(self, result: SendResult) -> tuple:
        """Stable key for a result row (row_number, or message_id)."""
        appointment = result.appointment
        if appointment is None:
            return ("msg", result.message_id or id(result))
        return ("row", appointment.row_number)

    def clear_results(self) -> None:
        """Remove all rows from the table."""
        self.setRowCount(0)
        self._row_keys.clear()

    def add_result(self, result: SendResult) -> None:
        """Add or update a row for the result (upsert by key)."""
        key = self._key_for(result)
        row = self._row_keys.get(key)
        if row is None:
            row = self.rowCount()
            self.insertRow(row)
            self._row_keys[key] = row

        appointment = result.appointment
        if appointment is None:
            date_str = ""
            time_str = ""
            patient_name = ""
        else:
            date_str = appointment.start_time.strftime("%Y-%m-%d")
            time_str = appointment.start_time.strftime("%H:%M")
            patient_name = appointment.patient_name

        label, color = self.STATUS_DISPLAY.get(
            result.status, ("❓ Desconocido", Qt.GlobalColor.gray)
        )
        error_text = result.error_reason or ""

        cells = [
            patient_name,
            result.phone_used,
            date_str,
            time_str,
            label,
            error_text,
        ]

        for col, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if col == 4:  # Status column
                item.setForeground(color)
            self.setItem(row, col, item)

        self.scrollToBottom()

    def set_results(self, results: list[SendResult]) -> None:
        """Replace all results in the table."""
        self.clear_results()
        for result in results:
            self.add_result(result)

    def get_summary(self) -> dict[str, int]:
        """Return a summary of current results."""
        delivered = 0
        pending = 0
        failed = 0
        for row in range(self.rowCount()):
            status_item = self.item(row, 4)
            if not status_item:
                continue
            text = status_item.text()
            if "Entregado" in text:
                delivered += 1
            elif "Pendiente" in text:
                pending += 1
            else:
                failed += 1
        return {
            "delivered": delivered,
            "pending": pending,
            "failed": failed,
            "total": self.rowCount(),
        }

    def collect_pending_failed(self, results: list[SendResult]) -> list[SendResult]:
        """Return the results that are pending or failed (re-sendable)."""
        resendable = [r for r in results if r.status in (SendStatus.PENDING, SendStatus.FAILED)]
        # Keep dedup by row_number (latest wins); drop results without appointment
        seen: dict[tuple, SendResult] = {}
        for r in resendable:
            if r.appointment is None:
                continue
            seen[r.appointment.row_number] = r
        return list(seen.values())