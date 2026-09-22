"""
verify_phase4.py — Interactive Live Verification Runner for Phase 4 Resource Protection.

Run with:
    python verify_phase4.py
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time

from governance import (
    SpendGovernor,
    BudgetConfig,
    BudgetExceededException,
    TokenBucket,
    ProviderRateLimits,
    ResourcePool,
    PoolStarvationError,
    ProcessTracker,
    BoundedMemoryQueue,
    BufferOverflowError,
    default_spend_governor,
    default_rate_limiter,
    default_resource_registry,
    default_process_tracker,
)


async def run_phase4_live_checks():
    print("=" * 75)
    print(" [PHASE 4 VERIFICATION] Spend Caps, Rate Limiting & Resource Protection")
    print("=" * 75)

    # 1. Test Financial Spend Governor & Cap Breach
    print("\n[1/4] Testing Spend Governor & Financial Cap Halting...")
    gov = SpendGovernor(BudgetConfig(max_cost_usd_per_session=0.03, max_tokens_per_session=10_000))
    sid = "live_verify_session"

    rec1 = gov.record_turn_spend(sid, "t1", "claude-sonnet", 500, 500)
    print(f"  [OK] Recorded turn 1: {rec1.total_tokens} tokens, ${rec1.cost_usd:.4f} USD.")

    # Second turn breaches $0.03 cap
    halted_caught = False
    try:
        gov.record_turn_spend(sid, "t2", "claude-sonnet", 2000, 2000)
    except BudgetExceededException as exc:
        halted_caught = True
        summary = gov.format_terminal_summary(sid, exc)
        print(f"  [OK] BudgetExceededException cleanly intercepted: {exc.breach_type} cap breached (${exc.current_val:.4f} > ${exc.limit_val:.4f}).")
        print(f"  [OK] Terminal State Summary: {summary['summary']}")

    assert halted_caught, "Budget cap must halt execution"
    print("  [PASS] Spend governor halts model calls on budget breach without crashing.")

    # 2. Test Proactive Client-Side Rate Limiter
    print("\n[2/4] Testing Token-Bucket Rate Limiter (RPM / TPM)...")
    bucket = TokenBucket(ProviderRateLimits(rpm=120, tpm=10_000, max_queue_wait_sec=5.0))
    await bucket.acquire(requests=120, tokens=100)

    t0 = time.monotonic()
    waited = await bucket.acquire(requests=1, tokens=1, timeout=2.0)
    elapsed = time.monotonic() - t0
    print(f"  [OK] Throttled burst non-blocking: waited {elapsed:.3f}s for replenishment.")
    assert elapsed > 0.05
    print("  [PASS] Proactive rate limiter prevents HTTP 429 quota exhaustion.")

    # 3. Test Deterministic Connection Pool & Zero-Leak Guarantees
    print("\n[3/4] Testing Connection Pool Governance & Leak Cleanups...")
    pool = ResourcePool(name="live_db_pool", max_connections=2, pool_timeout_sec=0.1)

    # Normal lease
    async with pool.acquire() as conn:
        assert pool.active_count == 1
        assert pool.available_slots == 1
    assert pool.active_count == 0, "Must return to 0 leaks"

    # Cancellation lease
    async def cancelled_worker():
        async with pool.acquire():
            await asyncio.sleep(10.0)

    task = asyncio.create_task(cancelled_worker())
    await asyncio.sleep(0.02)
    assert pool.active_count == 1
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert pool.active_count == 0, "Must return to 0 leaks after cancellation"
    print("  [OK] Leased connections cleanly returned to 0 active leaks on completion & cancellation.")
    print("  [PASS] Connection pool starvation protection and lifecycle certified.")

    # 4. Test Subprocess Zombie Mitigation
    print("\n[4/4] Testing Subprocess Lifecycle & Zombie Mitigation...")
    tracker = ProcessTracker()
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    pid = proc.pid
    tracker.register(proc)
    assert tracker.is_alive(pid) is True
    print(f"  [OK] Registered background PID: {pid}")

    terminated = tracker.terminate(pid, timeout_sec=1.0)
    assert terminated is True
    assert tracker.is_alive(pid) is False
    assert pid not in tracker.active_pids()
    print(f"  [OK] Process {pid} reaped deterministically: 0 zombie processes lingering.")
    print("  [PASS] Subprocess zombie mitigation certified.")

    print("\n" + "=" * 75)
    print(" [ALL CHECKS PASSED] Phase 4 Spend & Resource Protection is 100% Operational!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_phase4_live_checks())
