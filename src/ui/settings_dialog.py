"""Settings dialog — configure message template, country code, and bridge port."""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.models.appointment import Appointment
from src.models.settings import Settings
from src.services.settings_store import SettingsStore
from src.services.template_renderer import render_template, get_available_variables

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Dialog for configuring application settings.

    Features:
    - Message template editor with monospace font
    - Variable reference panel showing available {{variables}}
    - Default country code input
    - Bridge port input
    - Live preview of rendered message with sample data
    - Save/Cancel buttons
    """

    def __init__(
        self,
        settings: Settings,
        store: SettingsStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._store = store
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        """Initialize the dialog UI."""
        self.setWindowTitle("Configuración")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)

        layout = QVBoxLayout(self)

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

        # Variables panel
        vars_widget = QWidget()
        vars_layout = QVBoxLayout(vars_widget)
        vars_layout.setContentsMargins(0, 0, 0, 0)

        vars_label = QLabel("Variables disponibles:")
        vars_label.setStyleSheet("font-weight: bold;")
        vars_layout.addWidget(vars_label)

        for var in get_available_variables():
            var_label = QLabel(f"{{{{{var}}}}}")
            var_label.setStyleSheet(
                "font-family: monospace; color: #0066cc; padding: 2px;"
            )
            vars_layout.addWidget(var_label)

        vars_layout.addStretch()
        template_layout.addWidget(vars_widget, stretch=1)

        layout.addWidget(template_group)

        # --- General settings ---
        general_group = QGroupBox("Configuración General")
        form = QFormLayout(general_group)

        self._country_code_input = QLineEdit()
        self._country_code_input.setPlaceholderText("+34")
        self._country_code_input.setMaxLength(5)
        form.addRow("Código de país:", self._country_code_input)

        self._port_input = QSpinBox()
        self._port_input.setRange(1024, 65535)
        self._port_input.setValue(3001)
        form.addRow("Puerto del bridge:", self._port_input)

        layout.addWidget(general_group)

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

        layout.addWidget(preview_group)

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

    def _on_preview(self) -> None:
        """Generate a preview of the rendered message with sample data."""
        template = self._template_edit.toPlainText()

        # Create a sample appointment
        sample = Appointment(
            row_number=1,
            start_time=datetime(2026, 7, 15, 10, 30),
            duration_minutes=30,
            gabinete="Sala 3",
            patient_name="Juan García",
            appointment_type="Limpieza dental",
            phone_mobile="612345678",
            country_code=self._country_code_input.text() or "+34",
        )

        rendered = render_template(template, sample)
        self._preview_label.setPlainText(rendered)

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

        self.accept()
