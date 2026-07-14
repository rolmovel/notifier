"""Send worker — QThread that sends WhatsApp messages sequentially."""

from __future__ import annotations

import asyncio
import logging

from PySide6.QtCore import QThread, Signal

from src.models.appointment import Appointment
from src.models.send_result import SendResult, SendStatus
from src.services.template_renderer import render_template
from src.services.whatsapp_client import SEND_DELAY_SECONDS, WhatsAppClient

logger = logging.getLogger(__name__)


class SendWorker(QThread):
    """QThread worker that sends WhatsApp messages for a list of appointments.

    Signals:
        progress(int current, int total): Emitted after each send attempt.
        result_ready(SendResult): Emitted when a single send result is available.
        finished_signal(list[SendResult]): Emitted when all sends are complete.
        error(str): Emitted on a critical error.
    """

    progress = Signal(int, int)
    result_ready = Signal(object)  # SendResult
    finished_signal = Signal(list)  # list[SendResult]
    error = Signal(str)

    def __init__(
        self,
        appointments: list[Appointment],
        template: str,
        bridge_url: str = "http://127.0.0.1:3001",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._appointments = appointments
        self._template = template
        self._bridge_url = bridge_url
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the send loop."""
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:
        """Execute the send loop in a background thread."""
        results: list[SendResult] = []
        total = len(self._appointments)

        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        client = WhatsAppClient(self._bridge_url)

        try:
            for idx, appointment in enumerate(self._appointments):
                if self._cancelled:
                    logger.info("Send cancelled by user at %d/%d", idx, total)
                    break

                # Check if appointment is valid
                if not appointment.is_valid:
                    error_msg = "; ".join(appointment.validation_errors)
                    result = SendResult(
                        appointment=appointment,
                        status=SendStatus.FAILED,
                        phone_used=appointment.phone_normalized or "(sin teléfono)",
                        message_sent="(no enviado — datos inválidos)",
                        error_reason=error_msg,
                    )
                    results.append(result)
                    self.result_ready.emit(result)
                    self.progress.emit(idx + 1, total)
                    continue

                # Render the message
                message_text = render_template(self._template, appointment)

                # Send the message
                phone = appointment.phone_normalized or ""
                result = loop.run_until_complete(
                    client.send_message(phone, message_text, appointment)
                )
                results.append(result)
                self.result_ready.emit(result)
                self.progress.emit(idx + 1, total)

                # Delay between sends (except after the last one)
                if idx < total - 1 and not self._cancelled:
                    loop.run_until_complete(asyncio.sleep(SEND_DELAY_SECONDS))

        except Exception as exc:
            logger.error("Send worker error: %s", exc)
            self.error.emit(str(exc))
        finally:
            loop.run_until_complete(client.close())
            loop.close()

        self.finished_signal.emit(results)
