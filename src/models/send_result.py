"""SendResult model representing the outcome of a single send attempt."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel

from src.models.appointment import Appointment


class SendStatus(str, Enum):
    """Status of a send attempt."""

    SENT = "sent"
    FAILED = "failed"


class SendResult(BaseModel):
    """The outcome of attempting to send a WhatsApp message for one appointment."""

    appointment: Appointment
    status: SendStatus
    phone_used: str
    message_sent: str
    sent_at: Optional[datetime] = None
    error_reason: Optional[str] = None
    api_response: Optional[dict[str, Any]] = None
