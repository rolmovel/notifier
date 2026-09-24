"""Send queue — FIFO queue of messages pending dispatch, consumed one at a time."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from src.models.appointment import Appointment
from src.models.send_attempt import SendAttempt


@dataclass
class SendJob:
    """A single queued message waiting to be dispatched."""

    appointment: Appointment
    rendered_text: str
    attempts: list[SendAttempt] = field(default_factory=list)
    message_id: Optional[str] = None
    deadline: Optional[datetime] = None

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        """Whether the job's overall send deadline has passed."""
        if self.deadline is None:
            return False
        return (now or datetime.now()) > self.deadline


class SendQueue:
    """FIFO queue of messages pending dispatch.

    A single dispatcher consumes one job at a time (concurrency = 1) so the
    rate limiter and circuit breaker can keep WhatsApp traffic controlled.
    """

    def __init__(self) -> None:
        self._items: deque[SendJob] = deque()

    @property
    def size(self) -> int:
        return len(self._items)

    @property
    def is_empty(self) -> bool:
        return len(self._items) == 0

    def enqueue(self, job: SendJob, max_total_s: Optional[float] = None) -> None:
        """Add a job to the queue.

        Args:
            job: The job to queue.
            max_total_s: Optional per-message overall deadline (seconds from now).
        """
        if max_total_s is not None:
            job.deadline = datetime.now() + timedelta(seconds=max_total_s)
        self._items.append(job)

    def enqueue_many(self, jobs: list[SendJob], max_total_s: Optional[float] = None) -> None:
        """Add several jobs to the queue."""
        for job in jobs:
            self.enqueue(job, max_total_s=max_total_s)

    def dequeue(self) -> Optional[SendJob]:
        """Pop the next job, or None if the queue is empty."""
        if self._items:
            return self._items.popleft()
        return None

    def clear(self) -> None:
        self._items.clear()