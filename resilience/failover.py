"""
resilience/failover.py — Exponential Backoff with Jitter & Tiered Model Failover.

Provides:
  1. Retry policy with exponential backoff and randomized full jitter targeting
     transient HTTP 429, 500, 502, 503, 504, and network timeout errors.
  2. TieredModelFailover: Automatically falls back to secondary/tertiary model providers
     when the primary provider fails or its circuit breaker is OPEN.
  3. Seamless state continuity: downstream nodes and state graphs receive clean outputs
     with zero interruption.
  4. Explicit telemetry logging on failover events.
"""

from __future__ import annotations
from core.log_config import get_logger

import asyncio
import random
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from resilience.circuit_breaker import CircuitBreakerOpenError, default_breaker_registry
from telemetry import default_tracer


# Transient status codes / error signatures eligible for exponential backoff
TRANSIENT_ERROR_PATTERNS = [
    "429", "rate limit", "too many requests",
    "500", "502", "503", "504",
    "bad gateway", "service unavailable", "gateway timeout",
    "connection reset", "connection refused", "timeout", "timed out",
    "server disconnected", "overloaded",
]


def is_transient_error(exc: Exception) -> bool:
    """Detects whether an exception represents a transient upstream failure eligible for retry."""
    # CircuitBreakerOpenError is NOT transient on the same provider; it should trigger failover immediately!
    if isinstance(exc, CircuitBreakerOpenError):
        return False

    msg = str(exc).lower()
    for pattern in TRANSIENT_ERROR_PATTERNS:
        if pattern in msg:
            return True

    status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status_code in (429, 500, 502, 503, 504):
        return True

    return False


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    max_retries: int = 3
    base_delay_sec: float = 0.5
    multiplier: float = 2.0
    max_delay_sec: float = 10.0
    use_jitter: bool = True

    def calculate_delay(self, attempt: int) -> float:
        """Calculates exponential backoff with randomized full jitter."""
        raw_delay = min(self.max_delay_sec, self.base_delay_sec * (self.multiplier ** (attempt - 1)))
        if self.use_jitter:
            return random.uniform(0.1, raw_delay)
        return raw_delay


class FailoverResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    output: Any
    provider_used: str
    failover_occurred: bool
    fallback_reasons: List[str] = Field(default_factory=list)
    attempts: int = 1


async def execute_with_retry(
    call_fn: Callable[[], Coroutine[Any, Any, Any]],
    policy: Optional[RetryPolicy] = None,
    service_name: str = "upstream_service",
) -> Any:
    """
    Executes an async operation with exponential backoff and jitter.
    Retries transient errors; re-raises permanent errors or when retries are exhausted.
    """
    pol = policy or RetryPolicy()
    breaker = default_breaker_registry.get_breaker(service_name)

    for attempt in range(1, pol.max_retries + 1):
        try:
            async with breaker.protect():
                return await call_fn()
        except Exception as exc:
            if attempt == pol.max_retries or not is_transient_error(exc):
                raise

            delay = pol.calculate_delay(attempt)
            await asyncio.sleep(delay)

    raise RuntimeError("Unexpected exit from retry loop.")


class ModelProviderCandidate:
    """Defines a tiered model provider candidate with its call handler."""

    def __init__(
        self,
        name: str,
        caller: Callable[[str, str], Coroutine[Any, Any, str] | str],
        service_name: Optional[str] = None,
    ) -> None:
        self.name = name
        self.caller = caller
        self.service_name = service_name or name


class TieredModelFailover:
    """
    Orchestrates tiered model provider failover with exponential backoff and circuit breaker safety.
    """

    def __init__(
        self,
        providers: List[ModelProviderCandidate],
        retry_policy: Optional[RetryPolicy] = None,
        telemetry_engine: Optional[Any] = None,
    ) -> None:
        if not providers:
            raise ValueError("TieredModelFailover requires at least one provider candidate.")
        self.providers = providers
        self.retry_policy = retry_policy or RetryPolicy()
        self.telemetry = telemetry_engine

    async def execute(
        self,
        prompt: str,
        system_prompt: str = "",
        user_id: str = "boss",
    ) -> FailoverResult:
        """
        Attempts execution on the primary provider.
        If it fails or its circuit breaker is OPEN, smoothly falls back to secondary/tertiary providers.
        """
        fallback_reasons: List[str] = []
        total_attempts = 0

        for idx, candidate in enumerate(self.providers):
            breaker = default_breaker_registry.get_breaker(candidate.service_name)
            is_fallback = idx > 0

            # Check if breaker is already OPEN; skip without wasting network latency
            if breaker.state.value == "OPEN":
                reason = f"Provider '{candidate.name}' circuit is OPEN (fast-failed)."
                fallback_reasons.append(reason)
                continue

            for attempt in range(1, self.retry_policy.max_retries + 1):
                total_attempts += 1
                try:
                    async with breaker.protect():
                        res = candidate.caller(prompt, system_prompt)
                        if asyncio.iscoroutine(res):
                            res = await res

                    # Log telemetry if a fallback had to be used
                    if is_fallback:
                        self._log_failover_telemetry(
                            user_id=user_id,
                            primary_provider=self.providers[0].name,
                            fallback_provider=candidate.name,
                            reasons=fallback_reasons,
                        )

                    return FailoverResult(
                        output=res,
                        provider_used=candidate.name,
                        failover_occurred=is_fallback,
                        fallback_reasons=fallback_reasons,
                        attempts=total_attempts,
                    )
                except Exception as exc:
                    if attempt < self.retry_policy.max_retries and is_transient_error(exc):
                        delay = self.retry_policy.calculate_delay(attempt)
                        await asyncio.sleep(delay)
                        continue
                    else:
                        reason = f"Provider '{candidate.name}' failed on attempt {attempt}: {exc}"
                        fallback_reasons.append(reason)
                        break

        # All tiered providers exhausted
        all_reasons = " | ".join(fallback_reasons)
        raise RuntimeError(f"All {len(self.providers)} tiered model providers failed. Details: {all_reasons}")

    def _log_failover_telemetry(
        self,
        user_id: str,
        primary_provider: str,
        fallback_provider: str,
        reasons: List[str],
    ) -> None:
        if self.telemetry and hasattr(self.telemetry, "log_event"):
            try:
                self.telemetry.log_event(
                    user_id=user_id,
                    event_type="PROVIDER_FAILOVER",
                    module_id="failover_engine",
                    details={
                        "primary_provider": primary_provider,
                        "fallback_provider": fallback_provider,
                        "reasons": reasons,
                    },
                )
            except Exception as e:
                import logging
                logging.error(f"[AUDIT FAILURE] Failed to record PROVIDER_FAILOVER telemetry: {e}")
                raise RuntimeError(f"Audit trail integrity violation: {e}")


def create_default_failover_chain(
    gemini_caller: Optional[Callable[[str, str], Coroutine[Any, Any, str] | str]] = None,
    openrouter_caller: Optional[Callable[[str, str], Coroutine[Any, Any, str] | str]] = None,
    freellmapi_caller: Optional[Callable[[str, str], Coroutine[Any, Any, str] | str]] = None,
    retry_policy: Optional[RetryPolicy] = None,
    telemetry: Optional[Any] = None,
) -> TieredModelFailover:
    """
    Constructs a robust 3-tier model provider failover chain:
      Tier 1: Google Gemini (Primary low-latency sovereign engine)
      Tier 2: OpenRouter (DeepSeek / Claude bridge)
      Tier 3: FreeLLMAPI (Aggregated 34-provider free matrix at localhost:3001/v1)
    """
    candidates: List[ModelProviderCandidate] = []

    if gemini_caller:
        candidates.append(ModelProviderCandidate(
            name="gemini",
            caller=gemini_caller,
            service_name="gemini_api",
        ))

    if openrouter_caller:
        candidates.append(ModelProviderCandidate(
            name="openrouter",
            caller=openrouter_caller,
            service_name="openrouter_api",
        ))

    if freellmapi_caller:
        candidates.append(ModelProviderCandidate(
            name="freellmapi",
            caller=freellmapi_caller,
            service_name="freellmapi_gateway",
        ))

    if not candidates:
        # Dummy fallback candidate to satisfy initialization
        candidates.append(ModelProviderCandidate(
            name="default_fallback",
            caller=lambda p, s="": "Fallback response",
            service_name="default_fallback",
        ))

    return TieredModelFailover(
        providers=candidates,
        retry_policy=retry_policy,
        telemetry_engine=telemetry,
    )

_log = get_logger('failover')
