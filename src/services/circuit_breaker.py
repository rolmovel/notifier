"""Circuit breaker — pause all sends globally when WhatsApp rate-limits or errors pile up."""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"       # normal operation, sends allowed
    OPEN = "open"           # trip: all sends paused during cooldown
    HALF_OPEN = "half_open" # testing the waters after cooldown


class CircuitBreaker:
    """Global circuit breaker to avoid hammering WhatsApp with retries.

    When `consecutive_errors` reaches `threshold`, the circuit opens and
    every send is stopped for `cooldown_s` seconds. After the cooldown the
    circuit goes half-open; a single success closes it, another error reopens it.
    """

    def __init__(self, threshold: int = 3, cooldown_s: int = 60) -> None:
        self._threshold = max(1, int(threshold))
        # Allow small cooldowns (>0) so tests can exercise the transitions fast
        self._cooldown_s = max(0.01, float(cooldown_s))
        self._state = CircuitState.CLOSED
        self._consecutive_errors = 0
        self._opened_at = 0.0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._cooldown_elapsed():
            logger.info("Circuit breaker half-open after cooldown")
            self._state = CircuitState.HALF_OPEN
        return self._state

    @property
    def consecutive_errors(self) -> int:
        return self._consecutive_errors

    def _cooldown_elapsed(self) -> bool:
        return (time.monotonic() - self._opened_at) >= self._cooldown_s

    def allow_send(self) -> bool:
        """Whether a send may proceed now."""
        return self.state != CircuitState.OPEN

    async def wait_if_blocked(self) -> None:
        """If the circuit is open, wait until the cooldown elapses."""
        if self.state == CircuitState.OPEN:
            remaining = self._cooldown_s - (time.monotonic() - self._opened_at)
            if remaining > 0:
                logger.warning("Circuit breaker abierto — pausando envíos %.1fs", remaining)
                await asyncio.sleep(remaining)

    def record_success(self) -> None:
        """Record a successful send (closes the circuit if half-open)."""
        if self._state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker closed after success")
        self._state = CircuitState.CLOSED
        self._consecutive_errors = 0

    def record_error(self, is_retryable: bool = True) -> None:
        """Record a failed send.

        Args:
            is_retryable: whether the error is transient (429/5xx/timeout).
                Permanent errors (bad number, disconnected) do not trip the
                circuit but are not counted as successes either.
        """
        if not is_retryable:
            return
        self._consecutive_errors += 1
        if self._consecutive_errors >= self._threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            logger.warning(
                "Circuit breaker ABIERTO tras %d errores consecutivos — pausando todos los envíos",
                self._consecutive_errors,
            )