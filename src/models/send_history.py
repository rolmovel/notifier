"""SendSession model representing a complete sending session."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from src.models.send_result import SendResult


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
    def sent_count(self) -> int:
        """Number of successfully sent messages."""
        return sum(1 for r in self.results if r.status.value == "sent")

    @property
    def failed_count(self) -> int:
        """Number of failed messages."""
        return sum(1 for r in self.results if r.status.value == "failed")

    @property
    def pending_count(self) -> int:
        """Number of appointments not yet processed."""
        return self.total_appointments - len(self.results)
