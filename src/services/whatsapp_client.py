"""WhatsApp client — async HTTP client calling the Baileys bridge endpoints."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import httpx

from src.models.send_result import SendResult, SendStatus

logger = logging.getLogger(__name__)

# HTTP status codes that should trigger retries
_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}

# Exponential backoff delays in seconds (5s, 10s, 20s)
_BACKOFF_DELAYS = [5, 10, 20]

# Maximum number of retry attempts
_MAX_RETRIES = 3

# Default delay between sends in seconds (1200ms)
SEND_DELAY_SECONDS = 1.2


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

    async def send_message(
        self,
        number: str,
        text: str,
        appointment=None,
    ) -> SendResult:
        """Send a WhatsApp message with retry logic.

        Args:
            number: Destination phone number in E.164 format.
            text: Message text to send.
            appointment: Optional Appointment object for the SendResult.

        Returns:
            SendResult with the outcome (sent or failed).
        """
        client = await self._get_client()

        last_error: str = ""

        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await client.post("/send", json={"number": number, "text": text})

                if response.status_code == 200:
                    data = response.json()
                    return SendResult(
                        appointment=appointment,
                        status=SendStatus.SENT,
                        phone_used=number,
                        message_sent=text,
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
                        api_response=error_data,
                    )

                # Retryable errors
                if response.status_code in _RETRYABLE_STATUS_CODES:
                    last_error = f"HTTP {response.status_code}"
                    if attempt < _MAX_RETRIES:
                        delay = _BACKOFF_DELAYS[attempt]
                        logger.warning(
                            "Send to %s failed (attempt %d/%d): %s. Retrying in %ds...",
                            number, attempt + 1, _MAX_RETRIES + 1, last_error, delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    break

                # Other HTTP errors
                last_error = f"HTTP {response.status_code}: {response.text}"
                break

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout,
                    httpx.PoolTimeout) as exc:
                last_error = f"Error de conexión: {exc}"
                if attempt < _MAX_RETRIES:
                    delay = _BACKOFF_DELAYS[attempt]
                    logger.warning(
                        "Send to %s failed (attempt %d/%d): %s. Retrying in %ds...",
                        number, attempt + 1, _MAX_RETRIES + 1, last_error, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                break
            except httpx.HTTPError as exc:
                last_error = f"Error HTTP: {exc}"
                break

        return SendResult(
            appointment=appointment,
            status=SendStatus.FAILED,
            phone_used=number,
            message_sent=text,
            error_reason=f"Máximo de reintentos excedido: {last_error}",
        )
