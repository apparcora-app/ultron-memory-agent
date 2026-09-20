"""
tests/test_phase4_resources.py — Automated Test Suite for Phase 4 Hardening.

Covers:
  1. Spend Cap Termination & Token Cost Governor (cost cap and token cap halts).
  2. Graceful terminal state transition on budget exhaustion (zero crash).
  3. Proactive client-side rate limiting (token bucket burst throttling & queueing).
  4. Rate limit queue timeout error handling.
  5. Deterministic connection pool governance & zero-leak guarantees (normal, error, cancellation).
  6. Connection pool starvation error handling.
  7. Centralized lifecycle shutdown hook (`shutdown_all`).
  8. Subprocess zombie mitigation & process tree termination.
  9. Bounded memory queue & buffer overflow protection.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from typing import Any, List

import pytest

from governance.spend_governor import (
    BudgetConfig,
    BudgetExceededException,
    SpendGovernor,
    calculate_cost_usd,
    default_spend_governor,
    lookup_model_rates,
)
from governance.rate_limiter import (
    AsyncRateLimiter,
    ProviderRateLimits,
    RateLimitQueueTimeoutError,
    TokenBucket,
    default_rate_limiter,
)
from governance.resource_registry import (
    ManagedResource,
    PoolStarvationError,
    ResourcePool,
    ResourceRegistry,
    default_resource_registry,
)
from governance.process_tracker import (
    BoundedMemoryQueue,
    BufferOverflowError,
    ProcessTracker,
    default_process_tracker,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── 1. Financial Budget Sentinel & Token Cost Governor ───────────────────────

def test_model_cost_table_rates():
    """Pricing rates must be defined accurately for standard models."""
    rates_sonnet = lookup_model_rates("claude-3-5-sonnet")
    assert rates_sonnet["input"] == 3.00
    assert rates_sonnet["output"] == 15.00

    rates_gemini = lookup_model_rates("gemini-2.0-flash")
    assert rates_gemini["input"] == 0.10
    assert rates_gemini["output"] == 0.40

    rates_deepseek = lookup_model_rates("deepseek-chat")
    assert rates_deepseek["input"] == 0.14

    # Calculate exact USD cost
    # 1,000 input tokens + 1,000 output tokens on Sonnet = (1000/1M)*3 + (1000/1M)*15 = $0.018
    cost = calculate_cost_usd("claude-3-5-sonnet", input_tokens=1000, output_tokens=1000)
    assert cost == 0.018


def test_spend_governor_cost_cap_breach():
    """SpendGovernor must halt immediately when the dollar expenditure cap is breached."""
    # Strict budget: max $0.05
    config = BudgetConfig(max_cost_usd_per_session=0.05, max_tokens_per_session=100_000)
    gov = SpendGovernor(config=config)
    session_id = "test_cost_breach"

    # Turn 1: 1,000 in, 1,000 out on Claude Sonnet (~$0.018) -> allowed
    rec1 = gov.record_turn_spend(session_id, "turn_1", "claude-sonnet", 1000, 1000)
    assert rec1.cost_usd == 0.018

    # Turn 2: 1,000 in, 1,000 out (~$0.018) -> total $0.036 -> allowed
    gov.record_turn_spend(session_id, "turn_2", "claude-sonnet", 1000, 1000)

    # Turn 3: 2,000 in, 2,000 out (~$0.036) -> total $0.072 -> breaches $0.05 limit!
    with pytest.raises(BudgetExceededException) as exc_info:
        gov.record_turn_spend(session_id, "turn_3", "claude-sonnet", 2000, 2000)

    err = exc_info.value
    assert err.breach_type == "cost"
    assert err.session_id == session_id
    assert err.current_val > 0.05
    assert err.limit_val == 0.05


def test_spend_governor_token_cap_breach():
    """SpendGovernor must halt immediately when the token quota cap is breached."""
    # Strict budget: max 5,000 tokens
    config = BudgetConfig(max_cost_usd_per_session=10.0, max_tokens_per_session=5000)
    gov = SpendGovernor(config=config)
    session_id = "test_token_breach"

    # Turn 1: 2,000 tokens -> allowed
    gov.record_turn_spend(session_id, "turn_1", "gemini-2.0-flash", 1000, 1000)

    # Pre-flight check with anticipated 4,000 tokens -> 2,000 + 4,000 = 6,000 > 5,000 limit!
    with pytest.raises(BudgetExceededException) as exc_info:
        gov.assert_within_budget(session_id, anticipated_tokens=4000)

    err = exc_info.value
    assert err.breach_type == "tokens"
    assert err.current_val == 6000.0
    assert err.limit_val == 5000.0


def test_spend_governor_graceful_terminal_state():
    """SpendGovernor must transition the session into a graceful terminal summary state."""
    config = BudgetConfig(max_cost_usd_per_session=0.02)
    gov = SpendGovernor(config=config)
    session_id = "test_terminal_state"

    gov.record_turn_spend(session_id, "turn_1", "claude-sonnet", 500, 500)

    exc = BudgetExceededException(
        session_id=session_id,
        breach_type="cost",
        current_val=0.035,
        limit_val=0.02,
        model="claude-sonnet",
    )
    terminal_summary = gov.format_terminal_summary(session_id, exc)

    assert terminal_summary["status"] == "HALTED_BUDGET_EXCEEDED"
    assert terminal_summary["terminal_state"] is True
    assert "Agent halted gracefully" in terminal_summary["summary"]


# ── 2. Proactive Client-Side Rate Limiter ────────────────────────────────────

@pytest.mark.anyio
async def test_rate_limiter_burst_throttling():
    """Burst of requests exceeding capacity must be throttled smoothly without dropping requests."""
    # Bucket capacity: 120 RPM (2 requests per second)
    limits = ProviderRateLimits(rpm=120, tpm=10_000, max_queue_wait_sec=5.0)
    bucket = TokenBucket(limits)

    # Empty the bucket
    await bucket.acquire(requests=120, tokens=100)

    # Next request must wait asynchronously for replenishment
    t0 = time.monotonic()
    waited = await bucket.acquire(requests=1, tokens=1, timeout=2.0)
    elapsed = time.monotonic() - t0

    assert elapsed >= 0.1  # Slept non-blocking while waiting for replenishment
    assert waited > 0.0


@pytest.mark.anyio
async def test_rate_limiter_queue_timeout_rejection():
    """Requests exceeding queue wait timeout must raise RateLimitQueueTimeoutError."""
    # Bucket capacity: 6 RPM (1 request every 10 seconds), timeout = 0.05s
    limits = ProviderRateLimits(rpm=6, tpm=100, max_queue_wait_sec=0.05)
    bucket = TokenBucket(limits)

    # Drain bucket
    await bucket.acquire(requests=6, tokens=100)

    # Request requiring another slot should time out because 10s > 0.05s
    with pytest.raises(RateLimitQueueTimeoutError) as exc_info:
        await bucket.acquire(requests=2, tokens=10, timeout=0.05)

    err = exc_info.value
    assert err.timeout_sec == 0.05
    assert err.requested_requests == 2


@pytest.mark.anyio
async def test_rate_limiter_context_manager():
    """AsyncRateLimiter context manager must govern model calls cleanly."""
    limiter = AsyncRateLimiter()
    async with limiter.limit("gemini", requests=1, tokens=50) as wait_time:
        assert isinstance(wait_time, float)


# ── 3. Connection Pool Governance & Deterministic Cleanup ────────────────────

@pytest.mark.anyio
async def test_connection_pool_deterministic_cleanup_on_success():
    """Checked-out connections must return to 0 active leaks upon normal completion."""
    pool = ResourcePool(name="db_pool", max_connections=5)
    assert pool.active_count == 0

    async with pool.acquire() as conn:
        assert conn.is_active is True
        assert pool.active_count == 1
        assert pool.available_slots == 4

    # Immediately after block exit, connection is closed and active leaks == 0
    assert conn.is_active is False
    assert pool.active_count == 0
    assert pool.available_slots == 5


@pytest.mark.anyio
async def test_connection_pool_deterministic_cleanup_on_exception():
    """Checked-out connections must return to 0 active leaks even when exceptions are raised."""
    pool = ResourcePool(name="http_pool", max_connections=3)

    try:
        async with pool.acquire() as conn:
            assert pool.active_count == 1
            raise ValueError("Simulated network failure")
    except ValueError:
        pass

    # Guaranteed release after error
    assert conn.is_active is False
    assert pool.active_count == 0
    assert pool.available_slots == 3


@pytest.mark.anyio
async def test_connection_pool_deterministic_cleanup_on_cancellation():
    """Checked-out connections must return to 0 active leaks upon asyncio.CancelledError."""
    pool = ResourcePool(name="mcp_pool", max_connections=2)

    async def cancelled_task():
        async with pool.acquire() as conn:
            await asyncio.sleep(10.0)

    task = asyncio.create_task(cancelled_task())
    await asyncio.sleep(0.05)  # Ensure task acquired connection
    assert pool.active_count == 1

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Connection must be cleanly returned to pool with 0 leaks
    assert pool.active_count == 0
    assert pool.available_slots == 2


@pytest.mark.anyio
async def test_connection_pool_starvation_prevention():
    """Exhausting pool capacity must raise PoolStarvationError once timeout expires."""
    pool = ResourcePool(name="strict_pool", max_connections=2, pool_timeout_sec=0.1)

    async def holder_task():
        async with pool.acquire():
            await asyncio.sleep(0.5)

    # Lease both slots
    h1 = asyncio.create_task(holder_task())
    h2 = asyncio.create_task(holder_task())
    await asyncio.sleep(0.02)

    assert pool.active_count == 2
    assert pool.available_slots == 0

    # Third acquisition must be rejected with PoolStarvationError
    with pytest.raises(PoolStarvationError) as exc_info:
        async with pool.acquire(timeout=0.05):
            pass  # pragma: no cover

    assert exc_info.value.pool_name == "strict_pool"
    assert exc_info.value.max_connections == 2

    # Clean up holders
    h1.cancel()
    h2.cancel()
    await asyncio.gather(h1, h2, return_exceptions=True)
    assert pool.active_count == 0


@pytest.mark.anyio
async def test_resource_registry_shutdown_all():
    """ResourceRegistry.shutdown_all must cleanly terminate all active pools and cleanup hooks."""
    registry = ResourceRegistry()
    pool1 = registry.register_pool("pool1", max_connections=5)
    pool2 = registry.register_pool("pool2", max_connections=5)

    cleanup_called = False

    def on_shutdown():
        nonlocal cleanup_called
        cleanup_called = True

    registry.register_cleanup_hook(on_shutdown)

    await registry.shutdown_all()

    assert cleanup_called is True
    assert registry.active_leak_count() == 0


# ── 4. Subprocess & Buffer Queue Guardrails ──────────────────────────────────

def test_subprocess_zombie_mitigation():
    """ProcessTracker must register spawned processes and terminate them without leaving zombie PIDs."""
    tracker = ProcessTracker()

    # Spawn a sleeping python subprocess
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    pid = proc.pid
    tracker.register(proc)

    try:
        assert tracker.is_alive(pid) is True
        assert pid in tracker.active_pids()

        # Terminate via two-stage process tracker
        terminated = tracker.terminate(pid, timeout_sec=1.0)
        assert terminated is True

        # Assert process is dead and zero zombies linger
        assert tracker.is_alive(pid) is False
        assert pid not in tracker.active_pids()
    finally:
        # Failsafe cleanup
        tracker.cleanup_all()


def test_bounded_memory_queue_buffer_overflow():
    """BoundedMemoryQueue must enforce maxsize capacity and reject writes with BufferOverflowError."""
    queue = BoundedMemoryQueue(maxsize=3, name="audit_event_buffer")

    queue.put_nowait("item_1")
    queue.put_nowait("item_2")
    queue.put_nowait("item_3")

    assert queue.is_full is True
    assert queue.qsize == 3

    # Exceeding buffer capacity must raise BufferOverflowError
    with pytest.raises(BufferOverflowError) as exc_info:
        queue.put_nowait("item_4_overflow")

    err = exc_info.value
    assert err.buffer_name == "audit_event_buffer"
    assert err.current_size == 3
    assert err.max_size == 3
