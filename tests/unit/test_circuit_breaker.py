"""Unit tests for the CircuitBreaker."""

from __future__ import annotations

import time

from src.services.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    def test_initial_state_closed(self) -> None:
        breaker = CircuitBreaker(threshold=3, cooldown_s=60)
        assert breaker.state == CircuitState.CLOSED
        assert breaker.allow_send() is True

    def test_opens_at_threshold(self) -> None:
        breaker = CircuitBreaker(threshold=3, cooldown_s=60)
        breaker.record_error()
        breaker.record_error()
        assert breaker.allow_send() is True
        breaker.record_error()  # third consecutive → open
        assert breaker.state == CircuitState.OPEN
        assert breaker.allow_send() is False

    def test_success_resets_counter(self) -> None:
        breaker = CircuitBreaker(threshold=3, cooldown_s=60)
        breaker.record_error()
        breaker.record_error()
        breaker.record_success()
        assert breaker.consecutive_errors == 0
        assert breaker.state == CircuitState.CLOSED

    def test_permanent_errors_do_not_trip(self) -> None:
        breaker = CircuitBreaker(threshold=2, cooldown_s=60)
        for _ in range(10):
            breaker.record_error(is_retryable=False)
        assert breaker.state == CircuitState.CLOSED

    def test_half_open_after_cooldown(self) -> None:
        breaker = CircuitBreaker(threshold=1, cooldown_s=0.05)
        breaker.record_error()
        assert breaker.state == CircuitState.OPEN
        time.sleep(0.06)
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.allow_send() is True

    def test_success_closes_half_open(self) -> None:
        breaker = CircuitBreaker(threshold=1, cooldown_s=0.05)
        breaker.record_error()
        time.sleep(0.06)
        assert breaker.state == CircuitState.HALF_OPEN
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    def test_error_reopens_half_open(self) -> None:
        breaker = CircuitBreaker(threshold=1, cooldown_s=0.05)
        breaker.record_error()
        time.sleep(0.06)
        assert breaker.state == CircuitState.HALF_OPEN
        breaker.record_error()
        assert breaker.state == CircuitState.OPEN
        assert breaker.allow_send() is False

    async def test_wait_if_blocked_sleeps_until_cooldown(self) -> None:
        breaker = CircuitBreaker(threshold=1, cooldown_s=0.2)
        breaker.record_error()
        start = time.monotonic()
        await breaker.wait_if_blocked()
        assert breaker.allow_send() is True
        assert time.monotonic() - start >= 0.15