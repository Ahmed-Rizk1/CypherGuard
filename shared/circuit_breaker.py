"""
Circuit breaker pattern for external service calls.

Prevents cascading failures when a downstream service (e.g., OpenRouter LLM)
is unhealthy. After a threshold of consecutive failures, the circuit "opens"
and rejects all calls for a cooldown period, then allows a single test call
to probe recovery.

States:
    CLOSED    → Normal operation, all calls pass through
    OPEN      → Service is failing, all calls rejected immediately
    HALF_OPEN → Cooldown expired, allow one test call

Usage:
    from shared.circuit_breaker import CircuitBreaker

    llm_circuit = CircuitBreaker(name="openrouter", failure_threshold=3, recovery_timeout=60)

    if llm_circuit.can_execute():
        try:
            result = await call_llm(...)
            llm_circuit.record_success()
        except Exception:
            llm_circuit.record_failure()
    else:
        result = fallback_heuristic(...)
"""

import time
import logging
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """
    Thread-safe circuit breaker for protecting external service calls.

    Args:
        name: Human-readable identifier for logging.
        failure_threshold: Number of consecutive failures before opening.
        recovery_timeout: Seconds to wait in OPEN state before trying HALF_OPEN.
    """
    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 30.0

    _failure_count: int = field(default=0, init=False, repr=False)
    _success_count: int = field(default=0, init=False, repr=False)
    _last_failure_time: float = field(default=0.0, init=False, repr=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False, repr=False)
    _total_calls: int = field(default=0, init=False, repr=False)
    _total_failures: int = field(default=0, init=False, repr=False)
    _total_rejected: int = field(default=0, init=False, repr=False)

    @property
    def state(self) -> CircuitState:
        """Current state, with automatic OPEN → HALF_OPEN transition."""
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info(
                    f"Circuit '{self.name}' transitioning to HALF_OPEN "
                    f"after {elapsed:.1f}s cooldown"
                )
        return self._state

    def can_execute(self) -> bool:
        """Check if a call should be allowed through the circuit."""
        current_state = self.state

        if current_state == CircuitState.CLOSED:
            return True

        if current_state == CircuitState.HALF_OPEN:
            return True  # Allow one test request

        # OPEN — reject
        self._total_rejected += 1
        return False

    def record_success(self) -> None:
        """Record a successful call. Resets the circuit to CLOSED."""
        self._total_calls += 1
        self._success_count += 1

        if self._state == CircuitState.HALF_OPEN:
            logger.info(f"Circuit '{self.name}' recovered → CLOSED")

        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed call. May transition to OPEN."""
        self._total_calls += 1
        self._total_failures += 1
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            # Test call failed, go back to OPEN
            self._state = CircuitState.OPEN
            logger.warning(
                f"Circuit '{self.name}' test call failed → OPEN "
                f"(retry in {self.recovery_timeout}s)"
            )
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                f"Circuit '{self.name}' OPENED after {self._failure_count} "
                f"consecutive failures (cooldown: {self.recovery_timeout}s)"
            )

    def get_stats(self) -> dict:
        """Return circuit breaker statistics for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "total_calls": self._total_calls,
            "total_failures": self._total_failures,
            "total_rejected": self._total_rejected,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }
