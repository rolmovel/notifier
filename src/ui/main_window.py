"""Main window — primary application window."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.models.appointment import Appointment
from src.models.send_result import SendResult, SendStatus
from src.models.settings import Settings
from src.services.excel_reader import ExcelReadError, read_excel
from src.services.history_store import HistoryStore
from src.services.send_worker import SendWorker
from src.services.settings_store import SettingsStore
from src.services.whatsapp_client import WhatsAppClient
from src.services.csv_exporter import export_results_to_csv
from src.ui.history_view import HistoryView
from src.ui.qr_dialog import QrDialog
from src.ui.results_table import ResultsTable
from src.ui.settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Primary application window for the WhatsApp notifier."""

    def __init__(
        self,
        settings: Settings,
        bridge_url: str = "http://127.0.0.1:3001",
        settings_store: SettingsStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._bridge_url = bridge_url
        self._settings_store = settings_store
        self._whatsapp_client = WhatsAppClient(bridge_url)
        self._appointments: list[Appointment] = []
        self._send_worker: SendWorker | None = None
        self._results: list[SendResult] = []

        self._setup_ui()
        self._update_status_bar()

        # Auto-refresh status bar every 30 seconds
        from PySide6.QtCore import QTimer
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status_bar)
        self._status_timer.start(30000)

    def _setup_ui(self) -> None:
        """Initialize the main window UI."""
        self.setWindowTitle("WhatsApp Notifier")
        self.setMinimumSize(900, 600)

        # Set window icon if available
        from PySide6.QtGui import QIcon
        from pathlib import Path as PathLib
        import sys as _sys
        if getattr(_sys, "frozen", False):
            icon_path = PathLib(_sys.executable).parent / "assets" / "icon.png"
        else:
            icon_path = PathLib(__file__).parent.parent.parent / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Top toolbar ---
        toolbar = QHBoxLayout()

        self._select_btn = QPushButton("📂 Seleccionar Excel")
        self._select_btn.clicked.connect(self._on_select_file)
        toolbar.addWidget(self._select_btn)

        self._file_label = QLabel("Ningún archivo seleccionado")
        toolbar.addWidget(self._file_label, stretch=1)

        self._settings_btn = QPushButton("⚙ Configuración")
        self._settings_btn.clicked.connect(self._on_open_settings)
        toolbar.addWidget(self._settings_btn)

        layout.addLayout(toolbar)

        # --- Tab widget ---
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, stretch=1)

        # --- Send tab ---
        send_tab = QWidget()
        send_layout = QVBoxLayout(send_tab)

        # --- Preview table ---
        preview_label = QLabel("Vista previa de citas:")
        send_layout.addWidget(preview_label)

        self._preview_table = QTableWidget(0, 5)
        self._preview_table.setHorizontalHeaderLabels(
            ["Paciente", "Teléfono", "Fecha", "Hora", "Tipo"]
        )
        self._preview_table.setAlternatingRowColors(True)
        self._preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._preview_table.setMaximumHeight(180)
        send_layout.addWidget(self._preview_table)

        # --- Send button and progress ---
        send_btn_layout = QHBoxLayout()

        self._send_btn = QPushButton("📤 Enviar Recordatorios")
        self._send_btn.clicked.connect(self._on_send)
        self._send_btn.setEnabled(False)
        send_btn_layout.addWidget(self._send_btn)

        self._cancel_btn = QPushButton("⏹ Cancelar")
        self._cancel_btn.clicked.connect(self._on_cancel_send)
        self._cancel_btn.setEnabled(False)
        send_btn_layout.addWidget(self._cancel_btn)

        self._export_btn = QPushButton("💾 Exportar CSV")
        self._export_btn.clicked.connect(self._on_export_csv)
        self._export_btn.setEnabled(False)
        send_btn_layout.addWidget(self._export_btn)

        send_layout.addLayout(send_btn_layout)

        # --- Progress bar ---
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        send_layout.addWidget(self._progress)

        # --- Results table ---
        results_label = QLabel("Resultados:")
        send_layout.addWidget(results_label)

        self._results_table = ResultsTable()
        send_layout.addWidget(self._results_table, stretch=1)

        self._tabs.addTab(send_tab, "📤 Enviar")

        # --- History tab ---
        self._history_view = HistoryView()
        self._tabs.addTab(self._history_view, "📜 Historial")

        # --- Status bar ---
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("🔴 Desconectado")
        self._status_bar.addPermanentWidget(self._status_label)

    def _update_status_bar(self) -> None:
        """Update the WhatsApp connection status indicator."""
        import httpx
        try:
            resp = httpx.get(f"{self._bridge_url}/status", timeout=5.0)
            status = resp.json()
            state = status.get("state", "close")
            if state == "open":
                self._status_label.setText("🟢 Conectado")
            elif state == "connecting":
                self._status_label.setText("🟡 Conectando...")
            else:
                self._status_label.setText("🔴 Desconectado")
        except Exception:
            self._status_label.setText("🔴 Desconectado")

    def _on_open_settings(self) -> None:
        """Open the settings dialog."""
        dialog = SettingsDialog(self._settings, self._settings_store, self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            self._status_bar.showMessage("Configuración guardada", 3000)

    def _on_select_file(self) -> None:
        """Open file dialog to select an Excel file."""
        start_dir = ""
        if self._settings.last_file_path:
            start_dir = str(Path(self._settings.last_file_path).parent)

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo Excel",
            start_dir,
            "Excel files (*.xlsx)",
        )

        if not file_path:
            return

        try:
            appointments = read_excel(file_path, self._settings.default_country_code)
            self._appointments = appointments
            self._settings.last_file_path = file_path
            self._file_label.setText(Path(file_path).name)
            self._populate_preview(appointments)
            self._send_btn.setEnabled(len(appointments) > 0)
            self._status_bar.showMessage(
                f"Cargadas {len(appointments)} citas", 3000
            )
        except ExcelReadError as exc:
            QMessageBox.critical(self, "Error al leer Excel", str(exc))
        except Exception as exc:
            QMessageBox.critical(
                self, "Error", f"Error inesperado: {exc}"
            )

    def _populate_preview(self, appointments: list[Appointment]) -> None:
        """Fill the preview table with appointment data."""
        self._preview_table.setRowCount(0)
        for appt in appointments:
            row = self._preview_table.rowCount()
            self._preview_table.insertRow(row)
            self._preview_table.setItem(row, 0, QTableWidgetItem(appt.patient_name))
            self._preview_table.setItem(
                row, 1, QTableWidgetItem(appt.phone_normalized or "(inválido)")
            )
            self._preview_table.setItem(
                row, 2, QTableWidgetItem(appt.start_time.strftime("%Y-%m-%d"))
            )
            self._preview_table.setItem(
                row, 3, QTableWidgetItem(appt.start_time.strftime("%H:%M"))
            )
            self._preview_table.setItem(row, 4, QTableWidgetItem(appt.appointment_type))

    def _on_send(self) -> None:
        """Start sending WhatsApp messages."""
        if not self._appointments:
            return

        # Check WhatsApp connection
        import httpx
        try:
            resp = httpx.get(f"{self._bridge_url}/status", timeout=5.0)
            status = resp.json()
            state = status.get("state", "close")
            if state != "open":
                # Show QR dialog
                dialog = QrDialog(bridge_url=self._bridge_url, parent=self)
                result = dialog.exec()
                if result != QrDialog.DialogCode.Accepted:
                    QMessageBox.warning(
                        self,
                        "No conectado",
                        "Debe conectar WhatsApp antes de enviar mensajes.",
                    )
                    return
        except Exception as exc:
            QMessageBox.critical(
                self, "Error de conexión", f"No se pudo conectar con el bridge:\n{exc}"
            )
            return

        # Start the send worker
        self._results = []
        self._results_table.clear_results()
        self._send_worker = SendWorker(
            appointments=self._appointments,
            template=self._settings.message_template,
            bridge_url=self._bridge_url,
        )
        self._send_worker.progress.connect(self._on_progress)
        self._send_worker.result_ready.connect(self._on_result_ready)
        self._send_worker.finished_signal.connect(self._on_send_finished)
        self._send_worker.error.connect(self._on_send_error)

        self._send_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._select_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._progress.setMaximum(len(self._appointments))
        self._status_bar.showMessage("Enviando mensajes...")

        self._send_worker.start()

    def _on_cancel_send(self) -> None:
        """Cancel the ongoing send operation."""
        if self._send_worker and self._send_worker.isRunning():
            self._send_worker.cancel()
            self._status_bar.showMessage("Cancelando...", 2000)

    def _on_progress(self, current: int, total: int) -> None:
        """Update the progress bar."""
        self._progress.setValue(current)

    def _on_result_ready(self, result: SendResult) -> None:
        """Add a result to the table in real-time."""
        self._results.append(result)
        self._results_table.add_result(result)

    def _on_send_finished(self, results: list[SendResult]) -> None:
        """Handle send completion."""
        from datetime import datetime
        from src.models.send_history import SendSession

        sent = sum(1 for r in results if r.status == SendStatus.SENT)
        failed = sum(1 for r in results if r.status == SendStatus.FAILED)

        # Save to history
        try:
            session = SendSession(
                started_at=datetime.now(),
                completed_at=datetime.now(),
                source_file=self._settings.last_file_path or "",
                total_appointments=len(self._appointments),
                valid_appointments=sum(1 for a in self._appointments if a.is_valid),
                results=results,
            )
            HistoryStore().save_session(session)
            self._history_view.refresh()
        except Exception as exc:
            logger.warning("Failed to save session to history: %s", exc)

        self._send_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._select_btn.setEnabled(True)
        self._export_btn.setEnabled(len(results) > 0)
        self._progress.setVisible(False)

        self._status_bar.showMessage(
            f"Completado: {sent} enviados, {failed} fallidos", 5000
        )
        self._update_status_bar()

    def _on_send_error(self, error_msg: str) -> None:
        """Handle a critical send error."""
        QMessageBox.critical(self, "Error de envío", error_msg)
        self._send_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._select_btn.setEnabled(True)
        self._progress.setVisible(False)

    def _on_export_csv(self) -> None:
        """Export results to a CSV file."""
        if not self._results:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar resultados a CSV",
            "resultados_whatsapp.csv",
            "CSV files (*.csv)",
        )

        if not file_path:
            return

        try:
            export_results_to_csv(self._results, file_path)
            self._status_bar.showMessage(f"Exportado a {Path(file_path).name}", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "Error al exportar", str(exc))

    def closeEvent(self, event) -> None:
        """Clean up on window close."""
        # Stop the status timer
        self._status_timer.stop()

        if self._send_worker and self._send_worker.isRunning():
            self._send_worker.cancel()
            self._send_worker.wait(5000)

        super().closeEvent(event)
