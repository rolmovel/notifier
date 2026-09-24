"""SendStatus enum — the verified status of a WhatsApp message send."""

from __future__ import annotations

from enum import Enum
from typing import Optional


class SendStatus(str, Enum):
    """Status of a send attempt.

    Values:
        SENDING:   message accepted (queued) but no delivery receipt yet (transient).
        DELIVERED: delivery receipt received (DELIVERY_ACK or READ).
        PENDING:   server acknowledged but not yet delivered, within deadline.
        FAILED:    permanent error or timeout after exhausting retries.
    """

    SENDING = "sending"
    DELIVERED = "delivered"
    PENDING = "pending"
    ACCEPTED_NO_RECEIPT = "accepted_without_receipt"
    FAILED = "failed"

    @classmethod
    def _missing_(cls, value: object) -> Optional["SendStatus"]:
        # Accept legacy "sent" as delivered when deserializing old history.
        if isinstance(value, str) and value.lower() == "sent":
            return cls.DELIVERED
        return None