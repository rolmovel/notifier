"""Unit tests for WhatsAppClient accepted/message_id semantics and status lookup."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.models.appointment import Appointment
from src.models.send_result import SendStatus
from src.services.whatsapp_client import WhatsAppClient, backoff_with_jitter


def _make_appointment() -> Appointment:
    return Appointment(
        row_number=1,
        raw_data={
            "nombre del paciente": "Juan García",
            "hora de inicio": "2026-07-15 10:30",
            "tipo de cita": "Limpieza",
            "teléfono móvil": "612345678",
        },
        phone_header="teléfono móvil",
        country_code="+34",
    )


class TestSendMessageAccepted:
    async def test_200_accepted_is_sending_not_delivered(self, httpx_mock) -> None:
        httpx_mock.add_response(
            url="http://127.0.0.1:3001/send",
            method="POST",
            status_code=200,
            json={"accepted": True, "message_id": "ABC123", "status": "sending",
                  "timestamp": 1720000000},
        )
        client = WhatsAppClient("http://127.0.0.1:3001")
        result = await client.send_message("+34612345678", "Hola", _make_appointment())
        assert result.status == SendStatus.SENDING
        assert result.message_id == "ABC123"
        assert result.sent_at is not None
        await client.close()

    async def test_permanent_400_is_failed_not_retryable(self, httpx_mock) -> None:
        httpx_mock.add_response(
            url="http://127.0.0.1:3001/send",
            method="POST",
            status_code=400,
            json={"error": "Invalid number"},
        )
        client = WhatsAppClient("http://127.0.0.1:3001")
        result = await client.send_message("not-a-number", "Hola", _make_appointment())
        assert result.status == SendStatus.FAILED
        assert result.retryable is False
        assert "inválido" in (result.error_reason or "")
        await client.close()

    async def test_409_disconnected_is_failed(self, httpx_mock) -> None:
        httpx_mock.add_response(
            url="http://127.0.0.1:3001/send",
            method="POST",
            status_code=409,
            json={"error": "Not connected to WhatsApp"},
        )
        client = WhatsAppClient("http://127.0.0.1:3001")
        result = await client.send_message("+34612345678", "Hola")
        assert result.status == SendStatus.FAILED
        assert result.retryable is False
        assert "desconectado" in (result.error_reason or "")
        await client.close()

    async def test_retryable_429_then_success(self, httpx_mock) -> None:
        httpx_mock.add_response(
            url="http://127.0.0.1:3001/send",
            method="POST",
            status_code=429,
            json={"error": "Rate limited"},
        )
        httpx_mock.add_response(
            url="http://127.0.0.1:3001/send",
            method="POST",
            status_code=200,
            json={"accepted": True, "message_id": "DEF456", "status": "sending"},
        )
        client = WhatsAppClient("http://127.0.0.1:3001")
        result = await client.send_message("+34612345678", "Hola")
        assert result.status == SendStatus.SENDING
        assert result.message_id == "DEF456"
        await client.close()

    async def test_exhausted_retries_is_failed_retryable(self, httpx_mock, monkeypatch) -> None:
        # Speed up the backoff sleeps so the test runs fast
        import src.services.whatsapp_client as wc
        monkeypatch.setattr(wc, "backoff_with_jitter", lambda attempt, **kw: 0.01)

        # Always 503 — after max retries (4 attempts total) it must be FAILED retryable
        for _ in range(4):
            httpx_mock.add_response(
                url="http://127.0.0.1:3001/send",
                method="POST",
                status_code=503,
                json={"error": "Unavailable"},
            )
        client = WhatsAppClient("http://127.0.0.1:3001")
        result = await client.send_message("+34612345678", "Hola")
        assert result.status == SendStatus.FAILED
        assert result.retryable is True
        assert "reintentos" in (result.error_reason or "").lower()
        await client.close()


class TestGetMessageStatus:
    async def test_delivered_mapping(self, httpx_mock) -> None:
        httpx_mock.add_response(
            url="http://127.0.0.1:3001/message/ABC123",
            method="GET",
            status_code=200,
            json={"message_id": "ABC123", "status": "delivered",
                  "server_ack": True, "delivery_ack": True, "updated_at": 1720000001},
        )
        client = WhatsAppClient("http://127.0.0.1:3001")
        info = await client.get_message_status("ABC123")
        assert info["status"] == SendStatus.DELIVERED
        assert info["delivery_ack"] is True
        await client.close()

    async def test_pending_mapping(self, httpx_mock) -> None:
        httpx_mock.add_response(
            url="http://127.0.0.1:3001/message/ABC123",
            method="GET",
            status_code=200,
            json={"message_id": "ABC123", "status": "pending",
                  "server_ack": True, "delivery_ack": False, "updated_at": 1720000001},
        )
        client = WhatsAppClient("http://127.0.0.1:3001")
        info = await client.get_message_status("ABC123")
        assert info["status"] == SendStatus.PENDING
        await client.close()

    async def test_404_is_pending(self, httpx_mock) -> None:
        httpx_mock.add_response(
            url="http://127.0.0.1:3001/message/UNKNOWN",
            method="GET",
            status_code=404,
            json={"error": "Unknown message id"},
        )
        client = WhatsAppClient("http://127.0.0.1:3001")
        info = await client.get_message_status("UNKNOWN")
        assert info["status"] == SendStatus.PENDING
        await client.close()


class TestBackoffWithJitter:
    def test_grows_exponentially_and_stays_in_bounds(self) -> None:
        for attempt in range(0, 6):
            delay = backoff_with_jitter(attempt, base_ms=5000.0, cap_ms=60_000.0)
            cap = min(5000.0 * (2 ** max(0, attempt)), 60_000.0) / 1000.0
            assert 0.0 <= delay <= cap

    def test_never_negative(self) -> None:
        for attempt in range(0, 10):
            assert backoff_with_jitter(attempt) >= 0.0