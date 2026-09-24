"""Delivery tracker — verify the real delivery status of queued messages in the background."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Awaitable, Callable

from src.models.send_result import SendResult, SendStatus
from src.services.whatsapp_client import WhatsAppClient

logger = logging.getLogger(__name__)

# Poll interval and default deadline for delivery confirmation
_POLL_INTERVAL_S = 2.0
_DEFAULT_TIMEOUT_S = 45.0


class DeliveryTracker:
    """Polls the bridge for the delivery receipt of in-flight messages.

    A message accepted by the bridge (SENDING) is not "delivered" until the
    WhatsApp server confirms it. This tracker polls GET /message/{id} in the
    background until the receipt arrives, the message fails, or the deadline
    expires — never lying about delivery.
    """

    def __init__(
        self,
        client: WhatsAppClient,
        poll_interval_s: float = _POLL_INTERVAL_S,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        self._client = client
        self._poll_interval_s = max(0.5, float(poll_interval_s))
        self._timeout_s = max(1.0, float(timeout_s))

    async def track(self, result: SendResult) -> SendResult:
        """Poll until delivered/failed or timeout; return the updated SendResult.

        Args:
            result: A SendResult with status SENDING and a message_id.

        Returns:
            A new SendResult with the resolved status:
            - DELIVERED when the receipt confirms delivery
            - FAILED when the receipt reports an error
            - PENDING with a note when the deadline expires without confirmation
        """
        if result.message_id is None:
            # We never got an id — cannot verify; keep it honest as pending.
            return result.model_copy(
                update={
                    "status": SendStatus.PENDING,
                    "error_reason": result.error_reason or "Sin confirmación del bridge",
                }
            )

        deadline = time.monotonic() + self._timeout_s
        while True:
            info = await self._client.get_message_status(result.message_id)
            status = info.get("status", SendStatus.PENDING)
            logger.info(
                "Tracker poll %s: status=%s server_ack=%s delivery_ack=%s",
                result.message_id,
                status,
                info.get("server_ack"),
                info.get("delivery_ack"),
            )

            if status == SendStatus.DELIVERED:
                logger.info("Message %s delivered", result.message_id)
                return result.model_copy(
                    update={
                        "status": SendStatus.DELIVERED,
                        "delivered_at": datetime.now(),
                        "error_reason": None,
                    }
                )

            if status == SendStatus.FAILED:
                raw = info.get("raw") or {}
                reason = raw.get("error") or "Error de entrega reportado por WhatsApp"
                logger.warning("Message %s failed: %s", result.message_id, reason)
                return result.model_copy(
                    update={"status": SendStatus.FAILED, "error_reason": reason}
                )

            if time.monotonic() >= deadline:
                logger.warning(
                    "Message %s accepted but no receipt after %.0fs — marking accepted_without_receipt",
                    result.message_id, self._timeout_s,
                )
                return result.model_copy(
                    update={
                        "status": SendStatus.ACCEPTED_NO_RECEIPT,
                        "error_reason": f"Aceptado por WhatsApp, sin acuse de entrega en {int(self._timeout_s)}s",
                    }
                )

            await asyncio.sleep(self._poll_interval_s)

    def start_track(
        self,
        result: SendResult,
        on_done: Callable[[SendResult], Awaitable[None] | None],
    ):
        """Kick off background tracking on the currently running event loop.

        Must be called from inside a running asyncio loop (the worker thread).

        Args:
            result: The in-flight SendResult to track.
            on_done: Callback invoked with the resolved SendResult.

        Returns:
            The asyncio.Task created, so the caller can await it before
            closing the loop (otherwise the tracking would be cancelled).
        """
        loop = asyncio.get_running_loop()
        task = loop.create_task(self._run_track(result, on_done))
        return task

    async def _run_track(
        self,
        result: SendResult,
        on_done: Callable[[SendResult], Awaitable[None] | None],
    ) -> None:
        try:
            updated = await self.track(result)
            result = updated
        except Exception as exc:  # never let a tracking task kill the dispatch loop
            logger.error("DeliveryTracker error for %s: %s", result.message_id, exc)
            result = result.model_copy(
                update={"status": SendStatus.PENDING, "error_reason": f"Error de verificación: {exc}"}
            )
        finally:
            res = on_done(result)
            if asyncio.iscoroutine(res):
                await res