"""Unit tests for the extended SendStatus enum and result models."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.models.appointment import Appointment
from src.models.send_attempt import SendAttempt
from src.models.send_result import SendResult, SendStatus


def _make_appointment(row: int = 1) -> Appointment:
    return Appointment(
        row_number=row,
        raw_data={
            "nombre del paciente": "Juan García",
            "hora de inicio": "2026-07-15 10:30",
            "tipo de cita": "Limpieza",
            "teléfono móvil": "612345678",
        },
        phone_header="teléfono móvil",
        country_code="+34",
    )


class TestSendStatusEnum:
    def test_values(self) -> None:
        assert SendStatus.SENDING.value == "sending"
        assert SendStatus.DELIVERED.value == "delivered"
        assert SendStatus.PENDING.value == "pending"
        assert SendStatus.FAILED.value == "failed"

    def test_legacy_sent_maps_to_delivered(self) -> None:
        assert SendStatus("sent") == SendStatus.DELIVERED
        assert SendStatus("sent").value == "delivered"

    def test_accepted_without_receipt_value(self) -> None:
        assert SendStatus.ACCEPTED_NO_RECEIPT.value == "accepted_without_receipt"
        assert SendStatus.ACCEPTED_NO_RECEIPT != SendStatus.DELIVERED


class TestSendResultModel:
    def test_send_result_with_new_fields(self) -> None:
        result = SendResult(
            appointment=_make_appointment(),
            status=SendStatus.DELIVERED,
            phone_used="+34612345678",
            message_sent="Hola Juan",
            message_id="ABC123",
            sent_at=datetime(2026, 7, 15, 10, 31),
            delivered_at=datetime(2026, 7, 15, 10, 31, 5),
            attempts=[SendAttempt(attempt_number=1, started_at=datetime(2026, 7, 15, 10, 31),
                                  status=SendStatus.DELIVERED, message_id="ABC123")],
        )
        assert result.message_id == "ABC123"
        assert result.delivered_at is not None
        assert result.retryable is None
        assert len(result.attempts) == 1
        assert result.attempts[0].attempt_number == 1

    def test_legacy_status_deserializes(self) -> None:
        data = {
            "appointment": _make_appointment().model_dump(mode="json"),
            "status": "sent",  # legacy value from old history
            "phone_used": "+34612345678",
            "message_sent": "Hola",
        }
        result = SendResult(**data)
        assert result.status == SendStatus.DELIVERED

    def test_unknown_status_rejected(self) -> None:
        data = {
            "appointment": _make_appointment().model_dump(mode="json"),
            "status": "bogus",
            "phone_used": "+34612345678",
            "message_sent": "Hola",
        }
        with pytest.raises(ValidationError):
            SendResult(**data)

    def test_json_roundtrip_preserves_status(self) -> None:
        result = SendResult(
            appointment=_make_appointment(),
            status=SendStatus.PENDING,
            phone_used="+34612345678",
            message_sent="Hola",
            error_reason="Sin confirmación de entrega en 45s",
        )
        dumped = result.model_dump(mode="json")
        restored = SendResult(**dumped)
        assert restored.status == SendStatus.PENDING
        assert restored.error_reason == "Sin confirmación de entrega en 45s"


class TestSendAttemptModel:
    def test_minimal_attempt(self) -> None:
        attempt = SendAttempt(
            attempt_number=1,
            started_at=datetime(2026, 7, 15, 10, 31),
            status=SendStatus.SENDING,
        )
        assert attempt.error_reason is None
        assert attempt.message_id is None