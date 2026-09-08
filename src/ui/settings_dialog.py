"""Settings dialog — configure message template, country code, and bridge port."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.services.whatsapp_client import WhatsAppClient
from src.ui.qr_dialog import QrDialog

from src.models.appointment import Appointment
from src.models.settings import Settings
from src.services.excel_reader import ExcelReadError, read_excel, read_excel_headers
from src.services.settings_store import SettingsStore
from src.services.template_renderer import render_template

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Dialog for configuring application settings.

    Features:
    - Message template editor with monospace font
    - Variable reference panel showing the Excel file's headers as {{placeholders}}
    - "Seleccionar Excel" button when no file is loaded yet
    - Default country code input
    - Bridge port input
    - Live preview of rendered message with sample data from the file
    - Save/Cancel buttons
    """

    def __init__(
        self,
        settings: Settings,
        store: SettingsStore | None = None,
        bridge_url: str = "http://127.0.0.1:3001",
        excel_headers: list[str] | None = None,
        sample_raw_data: dict[str, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._store = store
        self._bridge_url = bridge_url
        self._whatsapp_client = WhatsAppClient(bridge_url)
        # Excel-derived state (may be refreshed from within the dialog)
        self._excel_headers: list[str] = list(excel_headers) if excel_headers else []
        self._sample_raw_data: dict[str, str] = dict(sample_raw_data) if sample_raw_data else {}
        self._setup_ui()
        self._load_settings()
        self._refresh_variables_panel()
        self._refresh_connection_status()

        # Auto-refresh connection status every 3 seconds
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_connection_status)
        self._status_timer.start(3000)

    def _setup_ui(self) -> None:
        """Initialize the dialog UI."""
        self.setWindowTitle("Configuración")
        self.setMinimumWidth(700)
        self.setMinimumHeight(520)

        layout = QVBoxLayout(self)

        # --- Tab widget ---
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, stretch=1)

        # === Tab 1: Mensajes ===
        msg_tab = QWidget()
        msg_layout = QVBoxLayout(msg_tab)

        # --- Template section ---
        template_group = QGroupBox("Plantilla de Mensaje")
        template_layout = QHBoxLayout(template_group)

        # Template editor
        self._template_edit = QPlainTextEdit()
        self._template_edit.setStyleSheet(
            "QPlainTextEdit { font-family: monospace; font-size: 13px; }"
        )
        self._template_edit.setPlaceholderText("Escribe la plantilla del mensaje...")
        template_layout.addWidget(self._template_edit, stretch=3)

        # Variables panel — populated dynamically from the Excel headers
        vars_widget = QWidget()
        vars_layout = QVBoxLayout(vars_widget)
        vars_layout.setContentsMargins(0, 0, 0, 0)

        vars_label = QLabel("Variables disponibles (cabeceras del Excel):")
        vars_label.setStyleSheet("font-weight: bold;")
        vars_label.setWordWrap(True)
        vars_layout.addWidget(vars_label)

        # Container that holds either the variable list or the "no file" notice.
        self._vars_list_container = QWidget()
        self._vars_list_layout = QVBoxLayout(self._vars_list_container)
        self._vars_list_layout.setContentsMargins(0, 0, 0, 0)
        vars_layout.addWidget(self._vars_list_container)

        # "Seleccionar Excel" button — always visible so a file can be (re)chosen
        self._select_excel_btn = QPushButton("📂 Seleccionar Excel")
        self._select_excel_btn.clicked.connect(self._on_select_excel)
        vars_layout.addWidget(self._select_excel_btn)

        # Hint about how placeholders work
        hint_label = QLabel(
            "Usa {{cabecera}} para insertar el valor de cada columna.\n"
            "Las cabeceras se obtienen del archivo Excel seleccionado."
        )
        hint_label.setStyleSheet("color: #666; font-size: 11px;")
        hint_label.setWordWrap(True)
        vars_layout.addWidget(hint_label)

        vars_layout.addStretch()
        template_layout.addWidget(vars_widget, stretch=1)

        msg_layout.addWidget(template_group, stretch=1)

        # --- Preview section ---
        preview_group = QGroupBox("Vista Previa")
        preview_layout = QVBoxLayout(preview_group)

        preview_btn = QPushButton("👁 Generar vista previa")
        preview_btn.clicked.connect(self._on_preview)
        preview_layout.addWidget(preview_btn)

        self._preview_label = QPlainTextEdit()
        self._preview_label.setReadOnly(True)
        self._preview_label.setStyleSheet(
            "QPlainTextEdit { font-family: monospace; font-size: 13px; "
            "background-color: #f5f5f5; }"
        )
        self._preview_label.setPlaceholderText(
            "Pulsa 'Generar vista previa' para ver el mensaje de ejemplo..."
        )
        self._preview_label.setMaximumHeight(150)
        preview_layout.addWidget(self._preview_label)

        msg_layout.addWidget(preview_group)
        self._tabs.addTab(msg_tab, "💬 Mensajes")

        # === Tab 2: Conexión ===
        conn_tab = QWidget()
        conn_tab_layout = QVBoxLayout(conn_tab)
        conn_tab_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- WhatsApp connection section ---
        conn_group = QGroupBox("Conexión WhatsApp")
        conn_group_layout = QVBoxLayout(conn_group)

        # Status row
        status_row = QHBoxLayout()
        status_label = QLabel("Estado:")
        status_label.setStyleSheet("font-weight: bold;")
        status_row.addWidget(status_label)

        self._conn_status_label = QLabel("🔴 Desconectado")
        self._conn_status_label.setStyleSheet("font-weight: bold; padding: 5px; font-size: 14px;")
        status_row.addWidget(self._conn_status_label, stretch=1)
        conn_group_layout.addLayout(status_row)

        # Instructions
        instructions = QLabel(
            "Para vincular un nuevo número:\n"
            "1. Pulsa '🔌 Desconectar' para cerrar la sesión actual\n"
            "2. Pulsa '🔗 Conectar' para abrir el código QR o emparejar por teléfono\n"
            "3. Escanea el QR o introduce el código de emparejamiento en WhatsApp"
        )
        instructions.setStyleSheet("color: #666; padding: 10px;")
        instructions.setWordWrap(True)
        conn_group_layout.addWidget(instructions)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._conn_connect_btn = QPushButton("🔗 Conectar")
        self._conn_connect_btn.clicked.connect(self._on_connect_whatsapp)
        self._conn_connect_btn.setMinimumWidth(120)
        btn_row.addWidget(self._conn_connect_btn)

        self._conn_disconnect_btn = QPushButton("🔌 Desconectar")
        self._conn_disconnect_btn.clicked.connect(self._on_disconnect_whatsapp)
        self._conn_disconnect_btn.setEnabled(False)
        self._conn_disconnect_btn.setMinimumWidth(120)
        btn_row.addWidget(self._conn_disconnect_btn)

        conn_group_layout.addLayout(btn_row)
        conn_tab_layout.addWidget(conn_group)

        # --- General settings ---
        general_group = QGroupBox("Configuración General")
        form = QFormLayout(general_group)

        self._country_code_input = QLineEdit()
        self._country_code_input.setPlaceholderText("+34")
        self._country_code_input.setMaxLength(5)
        form.addRow("Código de país:", self._country_code_input)

        # Mapping: which Excel header holds the destination phone number.
        self._phone_header_combo = QComboBox()
        self._phone_header_combo.setToolTip(
            "Selecciona la columna del Excel que contiene el número de teléfono "
            "al que se enviará el mensaje."
        )
        self._phone_header_combo.currentTextChanged.connect(
            self._on_phone_header_changed
        )
        form.addRow("Columna de teléfono:", self._phone_header_combo)

        self._port_input = QSpinBox()
        self._port_input.setRange(1024, 65535)
        self._port_input.setValue(3001)
        form.addRow("Puerto del bridge:", self._port_input)

        conn_tab_layout.addWidget(general_group)
        conn_tab_layout.addStretch()

        self._tabs.addTab(conn_tab, "🔗 Conexión")

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("💾 Guardar")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _load_settings(self) -> None:
        """Load current settings into the UI."""
        self._template_edit.setPlainText(self._settings.message_template)
        self._country_code_input.setText(self._settings.default_country_code)
        self._port_input.setValue(self._settings.bridge_port)
        self._refresh_phone_header_combo()

    def _refresh_connection_status(self) -> None:
        """Check and display the current WhatsApp connection status."""
        try:
            resp = httpx.get(f"{self._bridge_url}/status", timeout=3.0)
            status = resp.json()
            state = status.get("state", "close")
            if state == "open":
                self._conn_status_label.setText("🟢 Conectado")
                self._conn_connect_btn.setEnabled(False)
                self._conn_disconnect_btn.setEnabled(True)
            elif state == "connecting":
                self._conn_status_label.setText("🟡 Conectando...")
                self._conn_connect_btn.setEnabled(False)
                self._conn_disconnect_btn.setEnabled(True)
            else:
                self._conn_status_label.setText("🔴 Desconectado")
                self._conn_connect_btn.setEnabled(True)
                self._conn_disconnect_btn.setEnabled(False)
        except Exception:
            self._conn_status_label.setText("🔴 Desconectado")
            self._conn_connect_btn.setEnabled(True)
            self._conn_disconnect_btn.setEnabled(False)

    def _refresh_phone_header_combo(self) -> None:
        """Repopulate the phone-header combo from the loaded Excel headers."""
        self._phone_header_combo.blockSignals(True)
        self._phone_header_combo.clear()
        self._phone_header_combo.addItem("(no mapeado)")
        for header in self._excel_headers:
            if header and header.strip():
                self._phone_header_combo.addItem(header)
        # Restore the previously saved selection if present.
        saved = (self._settings.phone_header or "").strip()
        idx = 0
        if saved:
            for i in range(self._phone_header_combo.count()):
                if self._phone_header_combo.itemText(i) == saved:
                    idx = i
                    break
        self._phone_header_combo.setCurrentIndex(idx)
        self._phone_header_combo.blockSignals(False)

    def _on_phone_header_changed(self, text: str) -> None:
        """Persist the selected phone header into the in-memory settings."""
        self._settings.phone_header = "" if text == "(no mapeado)" else text

    def _on_connect_whatsapp(self) -> None:
        """Open the QR dialog to connect or re-link WhatsApp."""
        try:
            resp = httpx.get(f"{self._bridge_url}/status", timeout=3.0)
            status = resp.json()
            state = status.get("state", "close")
            if state == "open":
                QMessageBox.information(
                    self,
                    "Ya conectado",
                    "WhatsApp ya está conectado.\n\n"
                    "Para vincular un número diferente, primero\n"
                    "desconecta con el botón '🔌 Desconectar'.",
                )
                return
        except Exception as exc:
            QMessageBox.critical(
                self, "Error de conexión",
                f"No se pudo conectar con el bridge:\n{exc}",
            )
            return

        # Ask the bridge to start Baileys and generate a QR
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._whatsapp_client.connect())
        finally:
            loop.close()

        self._status_timer.stop()
        dialog = QrDialog(bridge_url=self._bridge_url, parent=self)
        dialog.exec()
        self._status_timer.start(3000)
        self._refresh_connection_status()

    def _on_disconnect_whatsapp(self) -> None:
        """Disconnect WhatsApp and clear auth state so a new number can be linked."""
        reply = QMessageBox.question(
            self,
            "Desconectar WhatsApp",
            "¿Seguro que quieres desconectar WhatsApp?\n\n"
            "Esto cerrará la sesión actual y permitirás\n"
            "vincular un número diferente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._conn_disconnect_btn.setEnabled(False)
        self._conn_status_label.setText("🟡 Desconectando...")

        # Run logout in a background thread to avoid freezing the UI
        import threading
        self._logout_result = None

        def do_logout() -> None:
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                self._logout_result = loop.run_until_complete(
                    self._whatsapp_client.logout()
                )
            except Exception:
                self._logout_result = False
            finally:
                loop.close()

        threading.Thread(target=do_logout, daemon=True).start()
        QTimer.singleShot(100, self._poll_logout)

    def _poll_logout(self) -> None:
        """Poll the background logout thread until it finishes."""
        if self._logout_result is None:
            QTimer.singleShot(100, self._poll_logout)
            return
        self._refresh_connection_status()
        if not self._logout_result:
            QMessageBox.warning(self, "Error", "No se pudo desconectar WhatsApp.")

    def _on_preview(self) -> None:
        """Generate a preview of the rendered message with sample data.

        Uses the first data row of the selected Excel file as the sample. If no
        file is loaded, the user is prompted to select one.
        """
        if not self._sample_raw_data:
            QMessageBox.information(
                self,
                "Vista previa no disponible",
                "Selecciona un archivo Excel para generar la vista previa.\n\n"
                "Usa el botón '📂 Seleccionar Excel' en el panel de variables.",
            )
            return

        template = self._template_edit.toPlainText()
        sample = Appointment(
            row_number=1,
            raw_data=self._sample_raw_data,
            phone_header=self._settings.phone_header,
            country_code=self._country_code_input.text() or "+34",
        )

        rendered = render_template(template, sample)
        self._preview_label.setPlainText(rendered)

    def _refresh_variables_panel(self) -> None:
        """Rebuild the variables list from the currently loaded Excel headers."""
        # Clear previous content
        while self._vars_list_layout.count():
            item = self._vars_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if self._excel_headers:
            for header in self._excel_headers:
                if not header or not header.strip():
                    continue
                var_label = QLabel(f"{{{{{header}}}}}")
                var_label.setStyleSheet(
                    "font-family: monospace; color: #0066cc; padding: 2px;"
                )
                var_label.setToolTip(f"Inserta el valor de la columna '{header}'")
                self._vars_list_layout.addWidget(var_label)
            self._vars_list_layout.addStretch()
        else:
            notice = QLabel(
                "⚠ No hay ningún archivo Excel seleccionado.\n"
                "Pulsa el botón inferior para seleccionarlo y ver las cabeceras "
                "disponibles como placeholders."
            )
            notice.setStyleSheet("color: #b8860b; padding: 6px;")
            notice.setWordWrap(True)
            self._vars_list_layout.addWidget(notice)
            self._vars_list_layout.addStretch()

    def _on_select_excel(self) -> None:
        """Open a file dialog to choose an Excel file and load its headers."""
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
            headers = read_excel_headers(file_path)
        except ExcelReadError as exc:
            QMessageBox.critical(self, "Error al leer Excel", str(exc))
            return

        # Read the first data row to use as a preview sample
        sample_raw: dict[str, str] = {}
        try:
            appointments = read_excel(
                file_path,
                phone_header=self._settings.phone_header,
                default_country_code=self._settings.default_country_code,
            )
            if appointments:
                sample_raw = dict(appointments[0].raw_data)
        except ExcelReadError as exc:
            QMessageBox.warning(
                self,
                "Aviso",
                f"Se leyeron las cabeceras pero el archivo tiene problemas:\n{exc}",
            )

        self._excel_headers = headers
        self._sample_raw_data = sample_raw
        self._settings.last_file_path = file_path
        self._refresh_variables_panel()
        self._refresh_phone_header_combo()
        self._status_bar_hint(f"Excel cargado: {Path(file_path).name}")

    def _status_bar_hint(self, message: str) -> None:
        """Show a transient hint message (best-effort, no status bar in dialog)."""
        logger.info(message)

    @property
    def excel_headers(self) -> list[str]:
        """Headers of the Excel file currently loaded in the dialog."""
        return list(self._excel_headers)

    @property
    def sample_raw_data(self) -> dict[str, str]:
        """First data row (header -> value) of the loaded Excel file."""
        return dict(self._sample_raw_data)

    def _on_save(self) -> None:
        """Save the settings."""
        self._settings.message_template = self._template_edit.toPlainText()
        self._settings.default_country_code = self._country_code_input.text().strip() or "+34"
        self._settings.bridge_port = self._port_input.value()

        if self._store:
            try:
                self._store.save(self._settings)
                logger.info("Settings saved via dialog")
            except Exception as exc:
                logger.error("Failed to save settings: %s", exc)

        self._status_timer.stop()
        self.accept()
