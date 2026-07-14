"""History view widget — browse past send sessions."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.services.history_store import HistoryStore
from src.ui.results_table import ResultsTable
from src.models.send_result import SendResult, SendStatus

logger = logging.getLogger(__name__)


class HistoryView(QWidget):
    """Widget for browsing past send sessions.

    Features:
    - Session list showing date, total/sent/failed counts
    - View Details button opening a read-only results table
    - Delete button to remove old sessions
    """

    def __init__(self, store: HistoryStore | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store or HistoryStore()
        self._current_file_path: str | None = None
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        """Initialize the widget UI."""
        layout = QVBoxLayout(self)

        # --- Header ---
        header = QLabel("📜 Historial de Envíos")
        header.setStyleSheet("font-size: 16px; font-weight: bold; margin: 5px;")
        layout.addWidget(header)

        # --- Session list ---
        self._session_list = QListWidget()
        self._session_list.setAlternatingRowColors(True)
        self._session_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._session_list, stretch=1)

        # --- Buttons ---
        btn_layout = QHBoxLayout()

        self._view_btn = QPushButton("👁 Ver Detalles")
        self._view_btn.clicked.connect(self._on_view_details)
        self._view_btn.setEnabled(False)
        btn_layout.addWidget(self._view_btn)

        self._delete_btn = QPushButton("🗑 Eliminar")
        self._delete_btn.clicked.connect(self._on_delete)
        self._delete_btn.setEnabled(False)
        btn_layout.addWidget(self._delete_btn)

        self._refresh_btn = QPushButton("🔄 Actualizar")
        self._refresh_btn.clicked.connect(self.refresh)
        btn_layout.addWidget(self._refresh_btn)

        layout.addLayout(btn_layout)

        # --- Details table (hidden by default) ---
        self._details_label = QLabel("")
        self._details_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self._details_label.setVisible(False)
        layout.addWidget(self._details_label)

        self._details_table = ResultsTable()
        self._details_table.setVisible(False)
        layout.addWidget(self._details_table, stretch=1)

    def refresh(self) -> None:
        """Reload the session list from the store."""
        self._session_list.clear()
        sessions = self._store.list_sessions()

        if not sessions:
            item = QListWidgetItem("No hay sesiones guardadas")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self._session_list.addItem(item)
            return

        for session in sessions:
            started = session["started_at"]
            if isinstance(started, str):
                from datetime import datetime
                try:
                    started = datetime.fromisoformat(started)
                except ValueError:
                    pass

            started_str = started.strftime("%Y-%m-%d %H:%M") if hasattr(started, "strftime") else str(started)
            source_name = Path(session["source_file"]).name if session["source_file"] else "(desconocido)"

            label = (
                f"{started_str} | {source_name} | "
                f"Total: {session['total_appointments']} | "
                f"✅ {session['sent_count']} | ❌ {session['failed_count']}"
            )

            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, session["file_path"])
            self._session_list.addItem(item)

    def _on_selection_changed(self) -> None:
        """Enable/disable buttons based on selection."""
        has_selection = self._session_list.currentItem() is not None
        # Don't enable for the "no sessions" placeholder
        if has_selection:
            item = self._session_list.currentItem()
            file_path = item.data(Qt.ItemDataRole.UserRole)
            has_selection = file_path is not None

        self._view_btn.setEnabled(has_selection)
        self._delete_btn.setEnabled(has_selection)

    def _on_view_details(self) -> None:
        """Show the details of the selected session."""
        item = self._session_list.currentItem()
        if not item:
            return

        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            return

        session = self._store.load_session(file_path)
        if not session:
            QMessageBox.warning(self, "Error", "No se pudo cargar la sesión.")
            return

        self._current_file_path = file_path

        # Show details label
        started_str = session.started_at.strftime("%Y-%m-%d %H:%M")
        self._details_label.setText(
            f"Detalles de la sesión del {started_str} — "
            f"{session.sent_count} enviados, {session.failed_count} fallidos"
        )
        self._details_label.setVisible(True)

        # Populate details table
        self._details_table.clear_results()
        for result in session.results:
            self._details_table.add_result(result)
        self._details_table.setVisible(True)

    def _on_delete(self) -> None:
        """Delete the selected session."""
        item = self._session_list.currentItem()
        if not item:
            return

        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            return

        reply = QMessageBox.question(
            self,
            "Eliminar sesión",
            "¿Estás seguro de que quieres eliminar esta sesión?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self._store.delete_session(file_path):
                self._details_label.setVisible(False)
                self._details_table.setVisible(False)
                self._details_table.clear_results()
                self.refresh()
            else:
                QMessageBox.warning(self, "Error", "No se pudo eliminar la sesión.")
