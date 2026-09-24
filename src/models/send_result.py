"""SendResult model representing the outcome of a single send attempt."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator

from src.models.appointment import Appointment
from src.models.send_attempt import SendAttempt
from src.models.send_status import SendStatus


class SendResult(BaseModel):
    """The outcome of attempting to send a WhatsApp message for one appointment."""

    appointment: Optional[Appointment] = None
    status: SendStatus
    phone_used: str
    message_sent: str
    message_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    error_reason: Optional[str] = None
    retryable: Optional[bool] = None
    api_response: Optional[dict[str, Any]] = None
    attempts: list[SendAttempt] = []

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: Any) -> Any:
        # Map legacy string "sent" -> SendStatus.DELIVERED (also handled by _missing_).
        if isinstance(value, str) and value.lower() == "sent":
            return SendStatus.DELIVERED
        return value
