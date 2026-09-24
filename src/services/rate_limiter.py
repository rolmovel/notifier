"""Rate limiter — enforce a minimum interval between sends to avoid saturating WhatsApp."""

from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Guarantees a minimum interval between consecutive sends.

    A single dispatcher consumes messages one at a time; this limiter
    ensures no two sends happen closer than `min_interval_ms`.

    Slots are reserved atomically: `wait_until_ready` advances the next
    allowed time by the interval for every caller, so concurrent callers are
    spaced correctly (a third caller waits behind the first two).
    """

    def __init__(self, min_interval_ms: int = 1500) -> None:
        self._min_interval_ms = min_interval_ms
        self._next_allowed_at = 0.0  # monotonic timestamp of the next free slot
        self._lock = asyncio.Lock()

    @property
    def min_interval_ms(self) -> int:
        return self._min_interval_ms

    @min_interval_ms.setter
    def min_interval_ms(self, value: int) -> None:
        self._min_interval_ms = max(0, int(value))

    def _interval_s(self) -> float:
        return self._min_interval_ms / 1000.0

    def _seconds_until_ready(self) -> float:
        return max(0.0, self._next_allowed_at - time.monotonic())

    async def wait_until_ready(self) -> None:
        """Reserve the next send slot, waiting until the interval allows it."""
        async with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next_allowed_at - now)
            # Reserve the slot *now* so concurrent callers queue behind it
            self._next_allowed_at = max(now, self._next_allowed_at) + self._interval_s()
            if delay > 0:
                await asyncio.sleep(delay)

    def record_send(self) -> None:
        """Mark a send slot as used (for immediate sends)."""
        now = time.monotonic()
        self._next_allowed_at = max(now, self._next_allowed_at) + self._interval_s()