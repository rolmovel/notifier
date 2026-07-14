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
    """Table widget showing send results with real-time updates."""

    HEADERS = [
        "Paciente",
        "Teléfono",
        "Fecha Cita",
        "Hora Cita",
        "Estado",
        "Error",
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(0, len(self.HEADERS), parent)
        self._setup_ui()

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

    def clear_results(self) -> None:
        """Remove all rows from the table."""
        self.setRowCount(0)

    def add_result(self, result: SendResult) -> None:
        """Add a single send result to the table."""
        row = self.rowCount()
        self.insertRow(row)

        appointment = result.appointment
        date_str = appointment.start_time.strftime("%Y-%m-%d")
        time_str = appointment.start_time.strftime("%H:%M")

        status_text = "✅ Enviado" if result.status == SendStatus.SENT else "❌ Fallido"
        error_text = result.error_reason or ""

        cells = [
            appointment.patient_name,
            result.phone_used,
            date_str,
            time_str,
            status_text,
            error_text,
        ]

        for col, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if col == 4:  # Status column
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
        for row in range(self.rowCount()):
            status_item = self.item(row, 4)
            if status_item:
                if "Enviado" in status_item.text():
                    sent += 1
                else:
                    failed += 1
        return {"sent": sent, "failed": failed, "total": self.rowCount()}
