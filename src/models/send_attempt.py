"""SendAttempt model representing a single send attempt for a message."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from src.models.send_status import SendStatus


class SendAttempt(BaseModel):
    """A single attempt to send a message.

    Used for auditability: each message keeps the record of every attempt
    (timestamp, resulting status, and reason if it failed).
    """

    attempt_number: int
    started_at: datetime
    status: SendStatus
    error_reason: Optional[str] = None
    message_id: Optional[str] = None
