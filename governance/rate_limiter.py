"""
governance/rate_limiter.py — Proactive Client-Side Rate Limiter (Token-Bucket / Sliding Window).

Provides:
  1. Dual constraints: Requests-Per-Minute (RPM) and Tokens-Per-Minute (TPM) per provider.
  2. Non-blocking async queueing: requests exceeding capacity wait asynchronously via asyncio.sleep.
  3. Strict queue wait timeout (default 30s) raising RateLimitQueueTimeoutError.
  4. Both context manager (`async with limiter.limit(...)`) and direct `acquire()` interfaces.
"""

from __future__ import annotations
from core.log_config import get_logger

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class RateLimitQueueTimeoutError(TimeoutError):
    """Raised when queuing for API capacity exceeds the maximum allowed wait timeout."""

    def __init__(
        self,
        provider: str,
        timeout_sec: float,
        requested_requests: int,
        requested_tokens: int,
    ) -> None:
        super().__init__(
            f"Rate limit queue wait timed out for provider '{provider}' after {timeout_sec:.2f}s. "
            f"Requested: {requested_requests} reqs, {requested_tokens} tokens. "
            f"Aborted to prevent upstream request buildup."
        )
        self.provider = provider
        self.timeout_sec = timeout_sec
        self.requested_requests = requested_requests
        self.requested_tokens = requested_tokens


class ProviderRateLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    rpm: int = 60          # Requests per minute
    tpm: int = 100_000     # Tokens per minute
    max_queue_wait_sec: float = 30.0


class TokenBucket:
    """
    Dual-constraint token bucket tracking both requests and token quotas
    over a sliding 60-second replenishment interval.
    """

    def __init__(self, limits: ProviderRateLimits) -> None:
        self.limits = limits
        self.request_capacity = float(limits.rpm)
        self.token_capacity = float(limits.tpm)

        self.requests = float(limits.rpm)
        self.tokens = float(limits.tpm)

        self.last_replenish_time = time.monotonic()
        self._lock = asyncio.Lock()

    def _replenish(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_replenish_time
        if elapsed <= 0:
            return

        # Replenish rates per second
        req_refill_rate = self.request_capacity / 60.0
        token_refill_rate = self.token_capacity / 60.0

        self.requests = min(self.request_capacity, self.requests + elapsed * req_refill_rate)
        self.tokens = min(self.token_capacity, self.tokens + elapsed * token_refill_rate)
        self.last_replenish_time = now

    def estimate_wait_seconds(self, reqs: int, toks: int) -> float:
        """Calculates seconds required until sufficient capacity is replenished."""
        self._replenish()

        req_needed = max(0.0, reqs - self.requests)
        tok_needed = max(0.0, toks - self.tokens)

        if req_needed == 0.0 and tok_needed == 0.0:
            return 0.0

        req_wait = (req_needed / (self.request_capacity / 60.0)) if req_needed > 0 else 0.0
        tok_wait = (tok_needed / (self.token_capacity / 60.0)) if tok_needed > 0 else 0.0
        return max(req_wait, tok_wait)

    async def acquire(
        self,
        requests: int = 1,
        tokens: int = 1,
        timeout: Optional[float] = None,
    ) -> float:
        """
        Attempts to acquire capacity, sleeping asynchronously until capacity exists.
        Raises RateLimitQueueTimeoutError if wait exceeds timeout.
        """
        max_wait = timeout if timeout is not None else self.limits.max_queue_wait_sec
        deadline = time.monotonic() + max_wait
        total_waited = 0.0

        while True:
            async with self._lock:
                wait_sec = self.estimate_wait_seconds(requests, tokens)
                if wait_sec <= 0.001:
                    # Grant capacity immediately
                    self.requests -= requests
                    self.tokens -= tokens
                    return total_waited

                remaining_timeout = deadline - time.monotonic()
                if wait_sec > remaining_timeout or remaining_timeout <= 0:
                    raise RateLimitQueueTimeoutError(
                        provider="provider",
                        timeout_sec=max_wait,
                        requested_requests=requests,
                        requested_tokens=tokens,
                    )

            # Sleep outside the lock so other tasks can proceed or check status
            sleep_duration = min(wait_sec, 0.5)
            await asyncio.sleep(sleep_duration)
            total_waited += sleep_duration


class AsyncRateLimiter:
    """
    Centralized rate limiter managing multiple upstream providers and tool call quotas.
    """

    def __init__(self, default_limits: Optional[ProviderRateLimits] = None) -> None:
        self._default_limits = default_limits or ProviderRateLimits()
        self._provider_limits: Dict[str, ProviderRateLimits] = {
            "anthropic":   ProviderRateLimits(rpm=50, tpm=100_000, max_queue_wait_sec=30.0),
            "openai":      ProviderRateLimits(rpm=60, tpm=150_000, max_queue_wait_sec=30.0),
            "gemini":      ProviderRateLimits(rpm=120, tpm=200_000, max_queue_wait_sec=30.0),
            "openrouter":  ProviderRateLimits(rpm=60, tpm=80_000, max_queue_wait_sec=30.0),
            "tools":       ProviderRateLimits(rpm=300, tpm=1_000_000, max_queue_wait_sec=15.0),
        }
        self._buckets: Dict[str, TokenBucket] = {}
        self._meta_lock = asyncio.Lock()

    def set_provider_limits(self, provider: str, limits: ProviderRateLimits) -> None:
        self._provider_limits[provider] = limits
        # Reset bucket if already exists
        if provider in self._buckets:
            self._buckets[provider] = TokenBucket(limits)

    def _get_bucket(self, provider: str) -> TokenBucket:
        bucket_key = provider
        try:
            from core.auth import current_caller_id
            caller = current_caller_id.get()
            if caller:
                bucket_key = f'{caller}:{provider}'
        except ImportError:
            pass
        if bucket_key not in self._buckets:
            limits = self._provider_limits.get(provider, self._default_limits)
            self._buckets[bucket_key] = TokenBucket(limits)
        return self._buckets[bucket_key]
        return self._buckets[provider]

    async def acquire(
        self,
        provider: str = "default",
        requests: int = 1,
        tokens: int = 1,
        timeout: Optional[float] = None,
    ) -> float:
        """
        Acquires rate limit capacity for `provider`.
        Returns total time waited in seconds.
        """
        bucket = self._get_bucket(provider)
        try:
            return await bucket.acquire(requests=requests, tokens=tokens, timeout=timeout)
        except RateLimitQueueTimeoutError as exc:
            exc.provider = provider
            raise exc

    @asynccontextmanager
    async def limit(
        self,
        provider: str = "default",
        requests: int = 1,
        tokens: int = 1,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[float]:
        """Async context manager wrapper around acquire."""
        wait_time = await self.acquire(
            provider=provider,
            requests=requests,
            tokens=tokens,
            timeout=timeout,
        )
        yield wait_time


# Global default rate limiter instance
default_rate_limiter = AsyncRateLimiter()

_log = get_logger('rate_limiter')
