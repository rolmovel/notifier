"""Results table widget — displays send results in a QTableWidget.

The data columns are taken dynamically from the Excel headers stored in each
appointment's ``raw_data``. Two fixed columns are appended: the send status
(delivered / pending / failed) and the error reason (if any).

Rows are keyed by the appointment row number (falling back to message_id) so
an in-flight result can be updated in place when the delivery tracker resolves
it, without duplicating rows.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)

from src.models.send_result import SendResult, SendStatus


class ResultsTable(QTableWidget):
    """Table widget showing send results with real-time updates."""

    # Fixed trailing columns (after the dynamic Excel columns).
    STATUS_COLUMN_LABEL = "Estado"
    ERROR_COLUMN_LABEL = "Error"

    # Status → (label, color)
    STATUS_DISPLAY = {
        SendStatus.DELIVERED: ("✅ Entregado", Qt.GlobalColor.darkGreen),
        SendStatus.SENDING: ("⏳ Pendiente", Qt.GlobalColor.darkYellow),
        SendStatus.PENDING: ("⏳ Pendiente", Qt.GlobalColor.darkYellow),
        SendStatus.ACCEPTED_NO_RECEIPT: ("⚠️ Aceptado sin acuse", Qt.GlobalColor.darkYellow),
        SendStatus.FAILED: ("❌ Fallido", Qt.GlobalColor.red),
    }

    def __init__(self, parent=None) -> None:
        super().__init__(0, 0, parent)
        self._data_headers: list[str] = []
        self._setup_ui()
        self._row_keys: dict[tuple, int] = {}  # key -> row index
        self._row_results: dict[int, SendResult] = {}

    def _setup_ui(self) -> None:
        """Initialize the table UI."""
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)

        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)

    @property
    def status_column(self) -> int:
        """Index of the status column, or -1 if not configured yet."""
        n = self.columnCount()
        return n - 2 if n >= 2 else -1

    def _ensure_columns(self, data_headers: list[str]) -> None:
        """Set up the column headers (dynamic + fixed) if they changed."""
        if data_headers == self._data_headers and self.columnCount() > 0:
            return
        self._data_headers = list(data_headers)
        labels = list(data_headers) + [self.STATUS_COLUMN_LABEL, self.ERROR_COLUMN_LABEL]
        self.setColumnCount(len(labels))
        self.setHorizontalHeaderLabels(labels)

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
        self._row_results.clear()

    def add_result(self, result: SendResult) -> None:
        """Add or update a row for the result (upsert by key)."""
        appointment = result.appointment
        if appointment is not None:
            data_headers = list(appointment.raw_data.keys())
        else:
            data_headers = self._data_headers
        self._ensure_columns(data_headers)

        key = self._key_for(result)
        row = self._row_keys.get(key)
        if row is None:
            row = self.rowCount()
            self.insertRow(row)
            self._row_keys[key] = row
        self._row_results[row] = result

        label, color = self.STATUS_DISPLAY.get(
            result.status, ("❓ Desconocido", Qt.GlobalColor.gray)
        )
        error_text = result.error_reason or ""

        if appointment is not None:
            cells = [appointment.get(h) for h in data_headers]
        else:
            cells = [""] * len(data_headers)
        cells.append(label)
        cells.append(error_text)

        status_col = len(data_headers)  # status column index
        for col, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if col == status_col:
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
        accepted_without_receipt = 0
        failed = 0
        status_col = self.status_column
        for row in range(self.rowCount()):
            if status_col < 0:
                continue
            status_item = self.item(row, status_col)
            if not status_item:
                continue
            text = status_item.text()
            if "Entregado" in text:
                delivered += 1
            elif "Pendiente" in text:
                pending += 1
            elif "Aceptado sin acuse" in text:
                accepted_without_receipt += 1
            else:
                failed += 1
        return {
            "delivered": delivered,
            "pending": pending,
            "accepted_without_receipt": accepted_without_receipt,
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

    def selected_results(self) -> list[SendResult]:
        """Return results for the currently selected table rows."""
        rows = sorted({index.row() for index in self.selectionModel().selectedRows()})
        return [self._row_results[row] for row in rows if row in self._row_results]


