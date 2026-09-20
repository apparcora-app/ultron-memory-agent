"""
guardrails/limits.py — Execution Boundary Caps & Timeout Middleware.

Provides:
  1. ExecutionLimitExceeded: Raised when iteration cap or timeout threshold is breached.
  2. TimeoutMiddleware: Wraps async tool dispatches in explicit timeouts (default 10.0s).
  3. RecursionLimiter: Enforces hard recursion limits (maximum 5 iterations per task loop).
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, TypeVar

MAX_RECURSION_LIMIT: int = 5
DEFAULT_TOOL_TIMEOUT_SEC: float = 10.0


class ExecutionLimitExceeded(RuntimeError):
    """
    Raised when an agentic execution loop breaches safety limits:
    - Recursion/iteration cap exceeded (runaway loops)
    - Tool execution timeout breached (stalled operations)
    """

    def __init__(
        self,
        message: str,
        current_step: int = 0,
        limit: int = MAX_RECURSION_LIMIT,
        reason: str = "recursion_limit_exceeded",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.current_step = current_step
        self.limit = limit
        self.reason = reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": "ExecutionLimitExceeded",
            "message": self.message,
            "current_step": self.current_step,
            "limit": self.limit,
            "reason": self.reason,
        }


T = TypeVar("T")


async def dispatch_with_timeout(
    coro: Awaitable[T],
    timeout_sec: float = DEFAULT_TOOL_TIMEOUT_SEC,
    tool_name: str = "unknown_tool",
) -> T:
    """
    Wraps an async tool dispatch in an explicit asyncio.wait_for timeout.
    If the timeout threshold is breached, raises ExecutionLimitExceeded.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_sec)
    except asyncio.TimeoutError as err:
        raise ExecutionLimitExceeded(
            message=f"Tool '{tool_name}' dispatch timed out after {timeout_sec:.1f}s.",
            reason="timeout_threshold_breached",
        ) from err


class RecursionLimiter:
    """
    Enforces a hard boundary cap on agentic tool loop iterations.
    Terminates runaway loops after max_iterations (default: 5).
    """

    def __init__(self, max_iterations: int = MAX_RECURSION_LIMIT) -> None:
        self.max_iterations = max_iterations
        self._current_step = 0

    @property
    def current_step(self) -> int:
        return self._current_step

    def step(self) -> int:
        """Increment and return current step. Raises if limit reached."""
        self._current_step += 1
        if self._current_step > self.max_iterations:
            raise ExecutionLimitExceeded(
                message=(
                    f"Execution loop breached hard boundary cap: reached step {self._current_step} "
                    f"exceeding max limit of {self.max_iterations} iterations."
                ),
                current_step=self._current_step,
                limit=self.max_iterations,
                reason="recursion_limit_exceeded",
            )
        return self._current_step

    def check(self, step: int) -> None:
        """Check if a given step number exceeds the max limit."""
        if step >= self.max_iterations:
            raise ExecutionLimitExceeded(
                message=(
                    f"Execution loop reached hard boundary limit of {self.max_iterations} "
                    f"iterations at step {step}."
                ),
                current_step=step,
                limit=self.max_iterations,
                reason="recursion_limit_exceeded",
            )

    def reset(self) -> None:
        self._current_step = 0
