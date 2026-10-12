"""
resilience/circuit_breaker.py — Three-State Circuit Breaker Pattern.

Provides:
  1. CircuitState: CLOSED (normal), OPEN (fast-fail), HALF_OPEN (probe test).
  2. CircuitBreakerOpenError: Immediate rejection when open without wasting network latency.
  3. Automatic transition after cooldown window into HALF_OPEN.
  4. Success reset to CLOSED, or immediate trip back to OPEN on probe failure.
  5. CircuitBreakerRegistry managing isolated breaker instances per upstream provider.
"""

from __future__ import annotations

import asyncio
import enum
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from pydantic import BaseModel, ConfigDict

from ultron.core.log_config import get_logger


class CircuitState(str, enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(RuntimeError):
    """Raised immediately when attempting to call an upstream service whose circuit is OPEN."""

    def __init__(
        self,
        service_name: str,
        cooldown_remaining_sec: float,
        consecutive_failures: int,
        message: str | None = None,
    ) -> None:
        msg = message or (
            f"Circuit breaker for upstream service '{service_name}' is OPEN "
            f"({consecutive_failures} consecutive failures). "
            f"Fast-failing request immediately; cooldown remaining: {cooldown_remaining_sec:.2f}s."
        )
        super().__init__(msg)
        self.service_name = service_name
        self.cooldown_remaining_sec = cooldown_remaining_sec
        self.consecutive_failures = consecutive_failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": "CircuitBreakerOpenError",
            "service_name": self.service_name,
            "cooldown_remaining_sec": round(self.cooldown_remaining_sec, 2),
            "consecutive_failures": self.consecutive_failures,
        }


class CircuitBreakerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    failure_threshold: int = 3
    cooldown_duration_sec: float = 30.0
    half_open_max_probes: int = 1


class CircuitBreaker:
    """
    Stateful circuit breaker protecting upstream network services against cascading failures.
    """

    def __init__(
        self,
        service_name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        self.service_name = service_name
        self.config = config or CircuitBreakerConfig()

        self._state: CircuitState = CircuitState.CLOSED
        self._consecutive_failures: int = 0
        self._opened_at: float | None = None
        self._half_open_probes_in_flight: int = 0
        self._half_open_successes: int = 0

        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Returns the dynamic state, evaluating whether cooldown has expired."""
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self.config.cooldown_duration_sec:
                self._state = CircuitState.HALF_OPEN
                self._half_open_probes_in_flight = 0
                self._half_open_successes = 0
        return self._state

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    def cooldown_remaining(self) -> float:
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            elapsed = time.monotonic() - self._opened_at
            return max(0.0, self.config.cooldown_duration_sec - elapsed)
        return 0.0

    def record_success(self) -> None:
        """Records an upstream successful response."""
        current = self.state
        if current == CircuitState.HALF_OPEN:
            self._half_open_successes += 1
            if self._half_open_successes >= self.config.half_open_max_probes:
                # Probe succeeded; fully heal circuit back to CLOSED
                self._state = CircuitState.CLOSED
                self._consecutive_failures = 0
                self._opened_at = None
                self._half_open_probes_in_flight = 0
        elif current == CircuitState.CLOSED:
            self._consecutive_failures = 0

    def record_failure(self, error: Exception | None = None) -> None:
        """Records an upstream failure. Trips breaker to OPEN if threshold breached."""
        current = self.state
        if current == CircuitState.HALF_OPEN:
            # Probe failed; immediately trip back to OPEN
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            self._half_open_probes_in_flight = 0
        elif current == CircuitState.CLOSED:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()

    def check_permission(self) -> None:
        """Pre-flight check: raises CircuitBreakerOpenError if circuit is OPEN."""
        current = self.state
        if current == CircuitState.OPEN:
            remaining = self.cooldown_remaining()
            raise CircuitBreakerOpenError(
                service_name=self.service_name,
                cooldown_remaining_sec=remaining,
                consecutive_failures=self._consecutive_failures,
            )
        elif current == CircuitState.HALF_OPEN:
            if self._half_open_probes_in_flight >= self.config.half_open_max_probes:
                raise CircuitBreakerOpenError(
                    service_name=self.service_name,
                    cooldown_remaining_sec=self.cooldown_remaining(),
                    consecutive_failures=self._consecutive_failures,
                    message=f"Circuit for '{self.service_name}' is HALF-OPEN: probe capacity ({self.config.half_open_max_probes}) in-flight.",
                )
            self._half_open_probes_in_flight += 1

    @asynccontextmanager
    async def protect(self) -> AsyncIterator[None]:
        """Async context manager guarding upstream coroutine calls."""
        async with self._lock:
            self.check_permission()

        try:
            yield
            async with self._lock:
                self.record_success()
        except Exception as exc:
            async with self._lock:
                self.record_failure(exc)
            raise

    @contextmanager
    def protect_sync(self) -> Iterator[None]:
        """Synchronous context manager guarding upstream blocking calls."""
        self.check_permission()
        try:
            yield
            self.record_success()
        except Exception as exc:
            self.record_failure(exc)
            raise

    def reset(self) -> None:
        """Manually forces circuit breaker back to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = None
        self._half_open_probes_in_flight = 0
        self._half_open_successes = 0


class CircuitBreakerRegistry:
    """
    Registry maintaining isolated circuit breakers for distinct external services.
    """

    def __init__(self, default_config: CircuitBreakerConfig | None = None) -> None:
        self.default_config = default_config or CircuitBreakerConfig()
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_breaker(
        self,
        service_name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreaker:
        if service_name not in self._breakers:
            cfg = config or self.default_config
            self._breakers[service_name] = CircuitBreaker(service_name=service_name, config=cfg)
        return self._breakers[service_name]

    def reset_all(self) -> None:
        for b in self._breakers.values():
            b.reset()


# Global default breaker registry
default_breaker_registry = CircuitBreakerRegistry()

_log = get_logger('circuit_breaker')
