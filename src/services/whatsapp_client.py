"""WhatsApp client — async HTTP client calling the Baileys bridge endpoints."""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime
from typing import Any

import httpx

from src.models.send_result import SendResult, SendStatus

logger = logging.getLogger(__name__)

# HTTP status codes that should trigger retries
_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}

# Exponential backoff base (ms) with jitter
_BACKOFF_BASE_MS = 5000.0

# Maximum number of retry attempts for transient errors
_MAX_RETRIES = 3

# Default delay between sends in seconds (1500ms)
SEND_DELAY_SECONDS = 1.5


def backoff_with_jitter(attempt: int, base_ms: float = _BACKOFF_BASE_MS, cap_ms: float = 60_000.0) -> float:
    """Exponential backoff with full jitter.

    delay = random.uniform(0, min(base * 2**attempt, cap))

    Full-jitter avoids synchronized retry bursts across messages.
    """
    exp = min(base_ms * (2 ** max(0, attempt)), cap_ms)
    return random.uniform(0.0, exp) / 1000.0


class WhatsAppClient:
    """Async HTTP client for the Baileys bridge."""

    def __init__(self, base_url: str = "http://127.0.0.1:3001") -> None:
        self._base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(30.0, connect=5.0),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get_status(self) -> dict[str, Any]:
        """Check the WhatsApp connection status.

        Returns:
            Dict with 'connected', 'state', and 'phone' keys.
        """
        client = await self._get_client()
        try:
            response = await client.get("/status")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            logger.error("Failed to get status: %s", exc)
            return {"connected": False, "state": "close", "phone": None}

    async def get_qr(self) -> dict[str, Any] | None:
        """Get the current QR code for pairing.

        Returns:
            Dict with 'qr_code' and 'expires_in' keys, or None if unavailable.
        """
        client = await self._get_client()
        try:
            response = await client.get("/qr")
            if response.status_code == 200:
                return response.json()
            if response.status_code == 409:
                logger.info("Already connected, no QR needed")
                return None
            if response.status_code == 503:
                logger.info("QR not yet available")
                return None
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Failed to get QR: %s", exc)
            return None
        return None

    async def request_pairing_code(self, phone: str) -> dict[str, Any] | None:
        """Request a pairing code for phone-based authentication.

        Args:
            phone: Phone number in E.164 format.

        Returns:
            Dict with 'pairing_code' and 'expires_in' keys, or None on error.
        """
        client = await self._get_client()
        try:
            response = await client.post("/pair", json={"phone": phone})
            if response.status_code == 200:
                return response.json()
            logger.error("Pairing failed: %s (status %d)", response.text, response.status_code)
            return None
        except httpx.HTTPError as exc:
            logger.error("Failed to request pairing code: %s", exc)
            return None

    async def connect(self) -> bool:
        """Request the bridge to start Baileys and begin pairing.

        Returns:
            True if the connect request was accepted, False on error.
        """
        client = await self._get_client()
        try:
            response = await client.post("/connect")
            if response.status_code in (200, 409):
                return True
            logger.error("Connect failed: %s (status %d)", response.text, response.status_code)
            return False
        except httpx.HTTPError as exc:
            logger.error("Failed to connect: %s", exc)
            return False

    async def logout(self) -> bool:
        """Logout from WhatsApp and clear auth state so a new number can be linked.

        Returns:
            True if logout succeeded, False on error.
        """
        client = await self._get_client()
        try:
            response = await client.post("/logout")
            if response.status_code == 200:
                logger.info("WhatsApp logged out successfully")
                return True
            logger.error("Logout failed: %s (status %d)", response.text, response.status_code)
            return False
        except httpx.HTTPError as exc:
            logger.error("Failed to logout: %s", exc)
            return False

    async def send_message(
        self,
        number: str,
        text: str,
        appointment=None,
    ) -> SendResult:
        """Send a WhatsApp message with bounded retry logic.

        NOTE: HTTP 200 from the bridge means the message was ACCEPTED (queued),
        not delivered. The caller must confirm delivery via `get_message_status`
        (see DeliveryTracker). The returned SendResult has status SENDING.

        Args:
            number: Destination phone number in E.164 format.
            text: Message text to send.
            appointment: Optional Appointment object for the SendResult.

        Returns:
            SendResult with the outcome (sending/delivered/failed).
        """
        client = await self._get_client()

        last_error: str = ""
        attempt_number = 1

        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await client.post("/send", json={"number": number, "text": text})

                if response.status_code == 200:
                    data = response.json()
                    message_id = data.get("message_id")
                    return SendResult(
                        appointment=appointment,
                        status=SendStatus.SENDING,
                        phone_used=number,
                        message_sent=text,
                        message_id=message_id,
                        sent_at=datetime.now(),
                        api_response=data,
                    )

                # Permanent errors — no retry
                if response.status_code in (400, 409):
                    error_data = {}
                    try:
                        error_data = response.json()
                    except Exception:
                        pass
                    error_msg = error_data.get("error", f"HTTP {response.status_code}")
                    if response.status_code == 400:
                        error_msg = "Número de teléfono inválido"
                    elif response.status_code == 409:
                        error_msg = "WhatsApp desconectado. Por favor, reconecte."
                    return SendResult(
                        appointment=appointment,
                        status=SendStatus.FAILED,
                        phone_used=number,
                        message_sent=text,
                        error_reason=error_msg,
                        retryable=False,
                        api_response=error_data,
                    )

                # Retryable errors
                if response.status_code in _RETRYABLE_STATUS_CODES:
                    last_error = f"HTTP {response.status_code}"
                    attempt_number += 1
                    if attempt < _MAX_RETRIES:
                        delay = backoff_with_jitter(attempt)
                        logger.warning(
                            "Send to %s failed (attempt %d/%d): %s. Retrying in %.1fs...",
                            number, attempt + 1, _MAX_RETRIES + 1, last_error, delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    break

                # Other HTTP errors
                last_error = f"HTTP {response.status_code}: {response.text}"
                attempt_number += 1
                break

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout,
                    httpx.PoolTimeout) as exc:
                last_error = f"Error de conexión: {exc}"
                attempt_number += 1
                if attempt < _MAX_RETRIES:
                    delay = backoff_with_jitter(attempt)
                    logger.warning(
                        "Send to %s failed (attempt %d/%d): %s. Retrying in %.1fs...",
                        number, attempt + 1, _MAX_RETRIES + 1, last_error, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                break
            except httpx.HTTPError as exc:
                last_error = f"Error HTTP: {exc}"
                attempt_number += 1
                break

        return SendResult(
            appointment=appointment,
            status=SendStatus.FAILED,
            phone_used=number,
            message_sent=text,
            error_reason=f"Máximo de reintentos excedido: {last_error}",
            retryable=True,
        )

    async def get_message_status(self, message_id: str) -> dict[str, Any]:
        """Query the real delivery status of a previously sent message.

        Args:
            message_id: The message id returned by POST /send.

        Returns:
            Dict with keys: status (SendStatus), server_ack, delivery_ack,
            updated_at, and raw response. On bridge/network error the status is
            PENDING (unknown → treat as not confirmed yet).
        """
        client = await self._get_client()
        try:
            response = await client.get(f"/message/{message_id}")
            if response.status_code == 200:
                data = response.json()
                raw_status = data.get("status", "sending")
                mapping = {
                    "delivered": SendStatus.DELIVERED,
                    "pending": SendStatus.PENDING,
                    "sending": SendStatus.SENDING,
                    "failed": SendStatus.FAILED,
                }
                return {
                    "status": mapping.get(raw_status, SendStatus.PENDING),
                    "server_ack": bool(data.get("server_ack", False)),
                    "delivery_ack": bool(data.get("delivery_ack", False)),
                    "updated_at": data.get("updated_at"),
                    "raw": data,
                }
            if response.status_code == 404:
                logger.info("Message %s not yet tracked by bridge", message_id)
                return {"status": SendStatus.PENDING, "server_ack": False,
                        "delivery_ack": False, "updated_at": None, "raw": {}}
            logger.warning("Status check for %s returned HTTP %d", message_id, response.status_code)
            return {"status": SendStatus.PENDING, "server_ack": False,
                    "delivery_ack": False, "updated_at": None, "raw": {}}
        except httpx.HTTPError as exc:
            logger.error("Failed to get message status %s: %s", message_id, exc)
            return {"status": SendStatus.PENDING, "server_ack": False,
                    "delivery_ack": False, "updated_at": None, "raw": {}}