"""Unit tests for the SendQueue."""

from __future__ import annotations

from datetime import datetime

from src.models.appointment import Appointment
from src.services.send_queue import SendJob, SendQueue


def _make_job(row: int = 1) -> SendJob:
    appointment = Appointment(
        row_number=row,
        raw_data={
            "nombre del paciente": f"Paciente {row}",
            "hora de inicio": "2026-07-15 10:30",
            "tipo de cita": "Limpieza",
            "teléfono móvil": "612345678",
        },
        phone_header="teléfono móvil",
        country_code="+34",
    )
    return SendJob(appointment=appointment, rendered_text=f"Hola {row}")


class TestSendQueue:
    def test_enqueue_dequeue_fifo(self) -> None:
        queue = SendQueue()
        queue.enqueue(_make_job(1))
        queue.enqueue(_make_job(2))
        assert queue.size == 2
        first = queue.dequeue()
        assert first is not None and first.appointment.row_number == 1
        second = queue.dequeue()
        assert second is not None and second.appointment.row_number == 2
        assert queue.is_empty

    def test_dequeue_empty_returns_none(self) -> None:
        queue = SendQueue()
        assert queue.dequeue() is None
        assert queue.is_empty

    def test_enqueue_many(self) -> None:
        queue = SendQueue()
        queue.enqueue_many([_make_job(1), _make_job(2), _make_job(3)])
        assert queue.size == 3

    def test_clear(self) -> None:
        queue = SendQueue()
        queue.enqueue(_make_job(1))
        queue.clear()
        assert queue.is_empty

    def test_job_attempt_count(self) -> None:
        from src.models.send_attempt import SendAttempt
        from src.models.send_result import SendStatus
        job = _make_job(1)
        assert job.attempt_count == 0
        job.attempts.append(SendAttempt(
            attempt_number=1, started_at=datetime(2026, 7, 15, 10, 30),
            status=SendStatus.SENDING,
        ))
        assert job.attempt_count == 1

    def test_job_expiry(self) -> None:
        from datetime import timedelta
        queue = SendQueue()
        job = _make_job(1)
        queue.enqueue(job, max_total_s=0.001)  # deadline basically now
        # enqueue set the deadline; simulate elapsed time is hard here, so
        # check that the deadline is set and is_expired works with a past now
        assert job.deadline is not None
        assert job.is_expired(now=datetime.now() + timedelta(minutes=1)) is True
        assert job.is_expired(now=datetime.now() - timedelta(minutes=1)) is False