"""Results table widget — displays send results in a QTableWidget.

The data columns are taken dynamically from the Excel headers stored in each
appointment's ``raw_data``. Two fixed columns are appended: the send status
and the error reason (if any).
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

    def __init__(self, parent=None) -> None:
        super().__init__(0, 0, parent)
        self._data_headers: list[str] = []
        self._setup_ui()

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

    def clear_results(self) -> None:
        """Remove all rows from the table."""
        self.setRowCount(0)

    def add_result(self, result: SendResult) -> None:
        """Add a single send result to the table."""
        appointment = result.appointment
        data_headers = list(appointment.raw_data.keys())
        self._ensure_columns(data_headers)

        row = self.rowCount()
        self.insertRow(row)

        status_text = "✅ Enviado" if result.status == SendStatus.SENT else "❌ Fallido"
        error_text = result.error_reason or ""

        cells = [appointment.get(h) for h in data_headers]
        cells.append(status_text)
        cells.append(error_text)

        status_col = len(data_headers)  # status column index
        for col, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if col == status_col:
                if result.status == SendStatus.SENT:
                    item.setForeground(Qt.GlobalColor.darkGreen)
                else:
                    item.setForeground(Qt.GlobalColor.red)
            self.setItem(row, col, item)

        self.scrollToBottom()

    def set_results(self, results: list[SendResult]) -> None:
        """Replace all results in the table."""
        self.clear_results()
        for result in results:
            self.add_result(result)

    def get_summary(self) -> dict[str, int]:
        """Return a summary of current results."""
        sent = 0
        failed = 0
        status_col = self.status_column
        for row in range(self.rowCount()):
            if status_col < 0:
                continue
            status_item = self.item(row, status_col)
            if status_item:
                if "Enviado" in status_item.text():
                    sent += 1
                else:
                    failed += 1
        return {"sent": sent, "failed": failed, "total": self.rowCount()}
