"""
Tests for shared/circuit_breaker.py
"""

import time
import pytest
from shared.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    """Tests for the circuit breaker pattern implementation."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_stays_closed_under_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_opens_at_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        # Failure count reset — need 3 more failures to open
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_transitions_to_half_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.can_execute() is True  # Allow one test call

    def test_half_open_success_closes(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_stats_tracking(self):
        cb = CircuitBreaker(name="test_stats", failure_threshold=5)
        cb.record_success()
        cb.record_success()
        cb.record_failure()

        stats = cb.get_stats()
        assert stats["name"] == "test_stats"
        assert stats["total_calls"] == 3
        assert stats["total_failures"] == 1
        assert stats["failure_count"] == 1
        assert stats["state"] == "closed"

    def test_open_rejects_and_counts(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=999)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        assert cb.can_execute() is False
        assert cb.can_execute() is False
        assert cb.get_stats()["total_rejected"] == 2
