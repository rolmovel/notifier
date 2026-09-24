"""Unit tests for the RateLimiter."""

from __future__ import annotations

import asyncio
import time

from src.services.rate_limiter import RateLimiter


class TestRateLimiter:
    async def test_first_send_immediate(self) -> None:
        limiter = RateLimiter(min_interval_ms=1500)
        start = time.monotonic()
        await limiter.wait_until_ready()
        assert time.monotonic() - start < 0.5

    async def test_second_send_respects_interval(self) -> None:
        limiter = RateLimiter(min_interval_ms=200)
        await limiter.wait_until_ready()
        start = time.monotonic()
        await limiter.wait_until_ready()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.19  # small tolerance for timer granularity

    async def test_zero_interval_no_delay(self) -> None:
        limiter = RateLimiter(min_interval_ms=0)
        start = time.monotonic()
        for _ in range(5):
            await limiter.wait_until_ready()
        assert time.monotonic() - start < 0.5

    async def test_concurrent_calls_serialized(self) -> None:
        limiter = RateLimiter(min_interval_ms=100)
        start = time.monotonic()
        await asyncio.gather(
            limiter.wait_until_ready(),
            limiter.wait_until_ready(),
            limiter.wait_until_ready(),
        )
        # 3 slots at 100ms apart → total >= ~200ms
        assert time.monotonic() - start >= 0.18

    def test_setter_clamps_negative(self) -> None:
        limiter = RateLimiter(min_interval_ms=100)
        limiter.min_interval_ms = -5
        assert limiter.min_interval_ms == 0

    def test_record_send_marks_slot(self) -> None:
        limiter = RateLimiter(min_interval_ms=10_000)
        limiter.record_send()
        assert limiter._seconds_until_ready() > 5.0