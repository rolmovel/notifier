"""SendSession model representing a complete sending session."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from src.models.send_result import SendResult, SendStatus


class SendSession(BaseModel):
    """A complete sending session (one Excel file processed)."""

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    started_at: datetime
    completed_at: datetime | None = None
    source_file: str
    total_appointments: int
    valid_appointments: int
    results: list[SendResult] = Field(default_factory=list)

    @property
    def delivered_count(self) -> int:
        """Number of messages with confirmed delivery."""
        return sum(1 for r in self.results if r.status == SendStatus.DELIVERED)

    @property
    def pending_count(self) -> int:
        """Number of messages still pending delivery (or in-flight)."""
        return sum(1 for r in self.results if r.status in (SendStatus.PENDING, SendStatus.SENDING))

    @property
    def accepted_without_receipt_count(self) -> int:
        """Number of accepted messages without a verifiable delivery receipt."""
        return sum(1 for r in self.results if r.status == SendStatus.ACCEPTED_NO_RECEIPT)

    @property
    def failed_count(self) -> int:
        """Number of failed messages."""
        return sum(1 for r in self.results if r.status == SendStatus.FAILED)

    # Backward-compat alias: previously "sent" meant accepted; keep for UI/history.
    @property
    def sent_count(self) -> int:
        """Number of successfully sent messages (alias of delivered_count)."""
        return self.delivered_count