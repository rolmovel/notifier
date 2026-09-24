"""Send worker — QThread that sends WhatsApp messages via a rate-limited async queue."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QThread, Signal

from src.models.appointment import Appointment
from src.models.send_attempt import SendAttempt
from src.models.send_result import SendResult, SendStatus
from src.services.circuit_breaker import CircuitBreaker
from src.services.delivery_tracker import DeliveryTracker
from src.services.rate_limiter import RateLimiter
from src.services.send_queue import SendJob, SendQueue
from src.services.template_renderer import render_template
from src.services.whatsapp_client import SEND_DELAY_SECONDS, WhatsAppClient

logger = logging.getLogger(__name__)

# Retry policy for messages that come back failed with transient errors
_MAX_WORKER_RETRIES = 3
_RETRY_BACKOFF_BASE_S = 5.0

# Candidate headers (case-insensitive) that usually hold the patient name,
# used only for log messages (the worker is schema-agnostic otherwise).
_NAME_HEADER_HINTS = ("nombre", "paciente", "patiente", "name", "patient")


def _patient_label(appointment) -> str:
    """Best-effort patient label for logs (falls back to the row number)."""
    if appointment is not None:
        raw = getattr(appointment, "raw_data", None) or {}
        lower = {k.strip().lower(): v for k, v in raw.items() if k and k.strip()}
        for hint in _NAME_HEADER_HINTS:
            for key, value in lower.items():
                if hint in key and value:
                    return str(value)
        return f"fila {appointment.row_number}"
    return "(sin cita)"


class SendWorker(QThread):
    """QThread worker that sends WhatsApp messages for a list of appointments.

    Dispatches one message at a time through a queue, respecting a rate
    limiter and a global circuit breaker, and confirms delivery in the
    background via the DeliveryTracker.

    Signals:
        progress(int current, int total): Emitted after each accepted send.
        result_ready(SendResult): Emitted when a result is available (status
            may update later from SENDING to DELIVERED/PENDING/FAILED).
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
        send_interval_ms: int = int(SEND_DELAY_SECONDS * 1000),
        delivery_timeout_s: float = 45.0,
        circuit_threshold: int = 3,
        circuit_cooldown_s: int = 60,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._appointments = appointments
        self._template = template
        self._bridge_url = bridge_url
        self._send_interval_ms = send_interval_ms
        self._delivery_timeout_s = delivery_timeout_s
        self._circuit_threshold = circuit_threshold
        self._circuit_cooldown_s = circuit_cooldown_s
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the send loop."""
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:
        """Execute the send loop in a background thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results: list[SendResult] = []

        client = WhatsAppClient(self._bridge_url)
        try:
            loop.run_until_complete(self._dispatch(loop, client, results))
        except Exception as exc:
            logger.error("Send worker error: %s", exc)
            self.error.emit(str(exc))
        finally:
            try:
                loop.run_until_complete(client.close())
            except Exception:
                pass
            loop.close()

        self.finished_signal.emit(results)

    async def _dispatch(
        self,
        loop: asyncio.AbstractEventLoop,
        client: WhatsAppClient,
        results: list[SendResult],
    ) -> None:
        """Coroutine that builds the queue and dispatches messages one at a time."""
        breaker = CircuitBreaker(
            threshold=self._circuit_threshold,
            cooldown_s=self._circuit_cooldown_s,
        )
        limiter = RateLimiter(min_interval_ms=self._send_interval_ms)
        tracker = DeliveryTracker(client, timeout_s=self._delivery_timeout_s)
        total = len(self._appointments)
        processed = 0

        def on_tracked(updated: SendResult) -> None:
            """Called by the DeliveryTracker when a receipt resolves."""
            for i, existing in enumerate(results):
                same_msg = (updated.message_id and existing.message_id == updated.message_id)
                same_row = (
                    existing.appointment is not None
                    and updated.appointment is not None
                    and existing.appointment.row_number == updated.appointment.row_number
                )
                if same_msg or same_row:
                    results[i] = updated
                    break
            else:
                results.append(updated)
            self.result_ready.emit(updated)

        # --- Build the queue of valid appointments (invalid ones fail fast) ---
        queue = SendQueue()
        for appointment in self._appointments:
            if not appointment.is_valid:
                error_msg = "; ".join(appointment.validation_errors)
                result = SendResult(
                    appointment=appointment,
                    status=SendStatus.FAILED,
                    phone_used=appointment.phone_normalized or "(sin teléfono)",
                    message_sent="(no enviado — datos inválidos)",
                    error_reason=error_msg,
                    retryable=False,
                )
                results.append(result)
                self.result_ready.emit(result)
                self.progress.emit(processed + 1, total)
                processed += 1
                continue

            message_text = render_template(self._template, appointment)
            queue.enqueue(
                SendJob(appointment=appointment, rendered_text=message_text),
                max_total_s=self._delivery_timeout_s * (_MAX_WORKER_RETRIES + 1),
            )

        # --- Dispatch loop: one message at a time, rate-limited ---
        while not queue.is_empty and not self._cancelled:
            await breaker.wait_if_blocked()
            if not breaker.allow_send():
                await asyncio.sleep(1.0)
                continue

            job = queue.dequeue()
            if job is None:
                break

            if job.is_expired():
                result = SendResult(
                    appointment=job.appointment,
                    status=SendStatus.FAILED,
                    phone_used=job.appointment.phone_normalized or "",
                    message_sent=job.rendered_text,
                    error_reason="Tiempo límite total agotado para este mensaje",
                    retryable=False,
                )
                self._upsert_result(results, result)
                self.result_ready.emit(result)
                self.progress.emit(processed + 1, total)
                processed += 1
                continue

            await limiter.wait_until_ready()

            final = await self._send_with_retries(
                job, client, breaker, tracker, results, on_tracked
            )
            if final is None:
                continue

            if final.status == SendStatus.SENDING:
                # Show the pending row now; the tracker will update it later.
                final = final.model_copy(update={"status": SendStatus.PENDING})

            self._upsert_result(results, final)
            self.result_ready.emit(final)
            self.progress.emit(processed + 1, total)
            processed += 1

    async def _send_with_retries(
        self,
        job: SendJob,
        client: WhatsAppClient,
        breaker: CircuitBreaker,
        tracker: DeliveryTracker,
        results: list[SendResult],
        on_tracked,
    ) -> Optional[SendResult]:
        """Send one job with bounded retries on transient failures.

        Returns the final SendResult after acceptance (SENDING), permanent
        failure, or retries exhausted. Accepted messages are handed to the
        DeliveryTracker for background confirmation.
        """
        attempt = 0
        while attempt <= _MAX_WORKER_RETRIES and not self._cancelled:
            attempt += 1
            job.attempts.append(SendAttempt(
                attempt_number=attempt,
                started_at=datetime.now(),
                status=SendStatus.SENDING,
            ))

            try:
                result = await client.send_message(
                    job.appointment.phone_normalized or "",
                    job.rendered_text,
                    job.appointment,
                )
            except Exception as exc:
                logger.error("Send worker error for %s: %s", _patient_label(job.appointment), exc)
                self.error.emit(str(exc))
                return SendResult(
                    appointment=job.appointment,
                    status=SendStatus.FAILED,
                    phone_used=job.appointment.phone_normalized or "",
                    message_sent=job.rendered_text,
                    error_reason=f"Error interno: {exc}",
                    retryable=True,
                )

            if result.status == SendStatus.SENDING and result.message_id:
                # Accepted — confirm delivery in the background.
                job.message_id = result.message_id
                job.attempts[-1].message_id = result.message_id
                breaker.record_success()
                tracker.start_track(result, on_tracked)
                return result

            if result.status == SendStatus.FAILED:
                job.attempts[-1].error_reason = result.error_reason
                if result.retryable is False or job.is_expired():
                    breaker.record_error(is_retryable=False)
                    return result
                # Transient failure — retry with backoff (bounded)
                breaker.record_error(is_retryable=True)
                if attempt <= _MAX_WORKER_RETRIES:
                    backoff = _RETRY_BACKOFF_BASE_S * (2 ** (attempt - 1))
                    logger.warning(
                        "Worker retry %d/%d for %s in %.1fs",
                        attempt, _MAX_WORKER_RETRIES, _patient_label(job.appointment), backoff,
                    )
                    await breaker.wait_if_blocked()
                    if not breaker.allow_send():
                        await asyncio.sleep(1.0)
                    await asyncio.sleep(backoff)
                    continue

            # Unexpected status (e.g. PENDING directly) — treat as in-flight
            breaker.record_success()
            tracker.start_track(result, on_tracked)
            return result

        return None

    @staticmethod
    def _upsert_result(results: list[SendResult], result: SendResult) -> None:
        """Replace an existing result with the same row_number, else append."""
        for i, existing in enumerate(results):
            if existing.appointment.row_number == result.appointment.row_number:
                results[i] = result
                return
        results.append(result)