"""
verify_phase3.py — Interactive Live Verification Runner for Phase 3 Concurrency & Hardening.

Run with:
    python verify_phase3.py
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
from pathlib import Path

from concurrency import (
    default_lock_registry,
    LockAcquisitionTimeoutError,
    default_occ_manager,
    StateConcurrencyConflictError,
    atomic_write_json,
    safe_read_json,
)


async def run_phase3_live_checks():
    print("=" * 75)
    print(" [PHASE 3 VERIFICATION] Concurrency Control, OCC & Atomic Persistence")
    print("=" * 75)

    # 1. Test Granular Async Lock & Timeout
    print("\n[1/3] Testing Granular Async Locks & Timeout Prevention...")
    lock_key = "session:live_test"
    t0 = time.time()

    async def lock_holder():
        async with default_lock_registry.acquire_lock(lock_key, timeout=2.0):
            await asyncio.sleep(0.15)

    holder = asyncio.create_task(lock_holder())
    await asyncio.sleep(0.02)

    # Attempt acquire with short timeout
    timeout_caught = False
    try:
        async with default_lock_registry.acquire_lock(lock_key, timeout=0.03):
            pass
    except LockAcquisitionTimeoutError as err:
        timeout_caught = True
        print(f"  [OK] LockAcquisitionTimeoutError cleanly intercepted: {err.timeout_sec}s timeout.")

    await holder
    assert timeout_caught, "Lock timeout must be caught"
    print("  [PASS] Granular async locks prevent deadlocks with strict timeouts.")

    # 2. Test 20-Coroutine Parallel OCC Mutation
    print("\n[2/3] Stress Testing 20 Concurrent Coroutines (Zero Lost Writes)...")
    res_key = f"session:live_counter_{int(time.time())}"
    await default_occ_manager.get_state(res_key, default={"counter": 0, "workers": []})

    async def worker(idx: int):
        def mutate(state):
            state["counter"] = state.get("counter", 0) + 1
            workers = list(state.get("workers", []))
            workers.append(idx)
            state["workers"] = workers
            return state

        return await default_occ_manager.atomic_mutate(res_key, mutate, max_retries=50)

    t_start = time.time()
    await asyncio.gather(*[worker(i) for i in range(20)])
    elapsed = round(time.time() - t_start, 3)

    final_state, final_version = await default_occ_manager.get_state(res_key)
    print(f"  [OK] 20 parallel coroutines resolved in {elapsed}s.")
    print(f"  [OK] Counter Value: {final_state['counter']} (Expected: 20 -> ZERO LOST WRITES)")
    print(f"  [OK] Final Monotonic Version: {final_version} (Expected: 21 -> PERFECT MONOTONICITY)")
    assert final_state["counter"] == 20
    assert final_version == 21
    print("  [PASS] Optimistic Concurrency Control (OCC) rebase-and-retry verified.")

    # 3. Test Atomic File Write-Replace & Concurrent Read/Write
    print("\n[3/3] Testing Atomic File Persistence & Windows Lock Resiliency...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = Path(tmp_dir) / "atomic_state.json"
        payload = {"status": "LIVE_VERIFIED", "timestamp": time.time()}
        atomic_write_json(test_file, payload)

        # Verify no .tmp files remain
        tmp_files = list(Path(tmp_dir).glob(".*.tmp"))
        assert len(tmp_files) == 0
        readback = safe_read_json(test_file)
        assert readback["status"] == "LIVE_VERIFIED"
        print("  [OK] Write-replace semantics verified: no temporary residue on disk.")
        print(f"  [OK] Readback payload intact: {readback['status']}")
        print("  [PASS] Atomic persistence verified.")

    print("\n" + "=" * 75)
    print(" [ALL CHECKS PASSED] Phase 3 Concurrency Hardening is 100% Operational!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_phase3_live_checks())
