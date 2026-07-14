"""QR dialog — display QR code or pairing code for WhatsApp pairing."""

from __future__ import annotations

import logging

import httpx
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class QrDialog(QDialog):
    """Dialog displaying QR code or pairing code for WhatsApp Web pairing.

    Shows the QR code image with a refresh button, and an alternative
    "pair by phone number" button that requests a pairing code from the bridge.
    Auto-closes when the connection is established.
    """

    def __init__(
        self,
        bridge_url: str = "http://127.0.0.1:3001",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._bridge_url = bridge_url
        self._setup_ui()
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._check_connection)
        self._poll_timer.start(2000)  # Check every 2 seconds

    def _setup_ui(self) -> None:
        """Initialize the dialog UI."""
        self.setWindowTitle("Conectar WhatsApp")
        self.setMinimumWidth(420)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Title label
        title = QLabel("Conectar WhatsApp")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)

        # Instructions
        instructions = QLabel(
            "1. Abre WhatsApp en tu teléfono\n"
            "2. Ve a Configuración → Dispositivos vinculados\n"
            "3. Toca 'Vincular un dispositivo'\n"
            "4. Escanea este código QR"
        )
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instructions.setStyleSheet("color: #666; margin: 5px;")
        layout.addWidget(instructions)

        # QR code label
        self._qr_label = QLabel("Cargando código QR...")
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.setMinimumSize(300, 300)
        self._qr_label.setStyleSheet(
            "background-color: white; border: 2px solid #ddd; margin: 10px;"
        )
        layout.addWidget(self._qr_label)

        # --- Button row ---
        btn_row = QHBoxLayout()

        # Refresh QR button
        refresh_btn = QPushButton("🔄 Actualizar QR")
        refresh_btn.clicked.connect(self._refresh_qr)
        btn_row.addWidget(refresh_btn)

        # Pair by phone button
        pair_btn = QPushButton("📱 Vincular por teléfono")
        pair_btn.clicked.connect(self._on_pair_by_phone)
        btn_row.addWidget(pair_btn)

        layout.addLayout(btn_row)

        # Cancel button
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

        # Load QR on show
        self._refresh_qr()

    def _refresh_qr(self) -> None:
        """Fetch and display the QR code using synchronous HTTP."""
        self._qr_label.setText("Cargando código QR...")

        try:
            resp = httpx.get(f"{self._bridge_url}/qr", timeout=5.0)
            data = resp.json()
            qr_code = data.get("qr_code")
            if qr_code:
                self._display_qr(qr_code)
            else:
                self._qr_label.setText(
                    "No hay código QR disponible.\n"
                    "La conexión puede estar en progreso.\n"
                    "Espera o pulsa 'Actualizar QR'."
                )
        except Exception as exc:
            logger.error("Failed to fetch QR: %s", exc)
            self._qr_label.setText(f"Error al obtener QR: {exc}")

    def _on_pair_by_phone(self) -> None:
        """Request a pairing code using the user's phone number."""
        # Ask for phone number
        phone, ok = QInputDialog.getText(
            self,
            "Vincular por teléfono",
            "Introduce tu número de teléfono\n(con código de país, ej: +34629071739):",
            text="",
        )

        if not ok or not phone.strip():
            return

        phone = phone.strip()

        # Request pairing code from bridge
        try:
            resp = httpx.post(
                f"{self._bridge_url}/pair",
                json={"phone": phone},
                timeout=10.0,
            )
            data = resp.json()

            if resp.status_code == 200 and data.get("pairing_code"):
                code = data["pairing_code"]
                # Format as XX-XX-XX-XX for readability
                formatted = f"{code[0:2]}-{code[2:4]}-{code[4:6]}-{code[6:8]}"
                self._qr_label.setText(
                    f"🔗 CÓDIGO DE EMPAREJAMIENTO\n\n"
                    f"  {formatted}\n\n"
                    f"Introduce este código en WhatsApp:\n"
                    f"Configuración → Dispositivos vinculados\n"
                    f"→ Vincular un dispositivo\n"
                    f"→ Vincular con número de teléfono\n\n"
                    f"El código expira en 90 segundos."
                )
                self._qr_label.setStyleSheet(
                    "background-color: #f0f8ff; border: 2px solid #4a90d9; "
                    "margin: 10px; font-size: 20px; font-weight: bold;"
                )
            else:
                error = data.get("error", "Error desconocido")
                self._qr_label.setText(f"Error al solicitar código:\n{error}")
        except Exception as exc:
            logger.error("Failed to request pairing code: %s", exc)
            self._qr_label.setText(f"Error al solicitar código:\n{exc}")

    def _display_qr(self, qr_string: str) -> None:
        """Render a QR code string as an image and display it."""
        # Reset style in case we showed a pairing code before
        self._qr_label.setStyleSheet(
            "background-color: white; border: 2px solid #ddd; margin: 10px;"
        )

        try:
            import qrcode
            import io

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=8,
                border=2,
            )
            qr.add_data(qr_string)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)

            qimage = QImage()
            qimage.loadFromData(buf.getvalue(), "PNG")
            pixmap = QPixmap.fromImage(qimage)

            self._qr_label.setPixmap(
                pixmap.scaled(
                    280, 280,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        except ImportError:
            # qrcode library not available — show the raw string
            logger.warning("qrcode library not available, showing raw string")
            self._qr_label.setText(
                f"Código QR (texto):\n{qr_string[:100]}...\n\n"
                "Instala 'qrcode' para mostrar la imagen."
            )
            self._qr_label.setWordWrap(True)
        except Exception as exc:
            logger.error("Failed to render QR: %s", exc)
            self._qr_label.setText(f"Error al mostrar QR: {exc}")

    def _check_connection(self) -> None:
        """Poll the bridge status and close dialog if connected."""
        try:
            resp = httpx.get(f"{self._bridge_url}/status", timeout=5.0)
            status = resp.json()
            if status.get("state") == "open":
                logger.info("WhatsApp connected, closing QR dialog")
                self._poll_timer.stop()
                self.accept()
        except Exception as exc:
            logger.debug("Connection check error: %s", exc)

    def closeEvent(self, event) -> None:
        """Stop the poll timer when the dialog is closed."""
        self._poll_timer.stop()
        super().closeEvent(event)
