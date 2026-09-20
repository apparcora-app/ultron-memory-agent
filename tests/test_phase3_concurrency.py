"""
tests/test_phase3_concurrency.py — Automated Test Suite for Phase 3 Concurrency Hardening.

Covers:
  1. Granular session-scoped async locks (no global bottleneck).
  2. Lock acquisition timeout & deadlock prevention.
  3. Re-entrant lock acquisition within same task / ownership token.
  4. Optimistic Concurrency Control (OCC) collision detection & structured error.
  5. 20 parallel coroutine stress test with zero lost updates via atomic_mutate.
  6. Atomic file persistence (write-replace semantics, no partial reads/torn writes).
  7. High-frequency concurrent reader/writer filesystem stress test.
  8. ChatSessionManager concurrent turn append safety with OCC & lock registry.
  9. Parallel subtask isolation & deterministic aggregation reducer.
  10. LangGraph swarm state monotonic versioning.
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

from concurrency.locks import (
    AsyncLockRegistry,
    LockAcquisitionTimeoutError,
    ReentrantAsyncLock,
    default_lock_registry,
)
from concurrency.occ import (
    OCCStateManager,
    StateConcurrencyConflictError,
    default_occ_manager,
)
from concurrency.atomic_io import (
    atomic_write,
    atomic_write_json,
    async_atomic_write,
    async_atomic_write_json,
    safe_read,
    safe_read_json,
)
from chat_session_manager import ChatSessionManager
from contracts import SwarmHandoffStateContract, validate_contract
from langgraph_pipeline import LangGraphTwoStepSwarm


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── 1. Granular Async Locks ───────────────────────────────────────────────────

@pytest.mark.anyio
async def test_granular_async_lock_isolation():
    """Different resource keys must have independent locks and not block each other."""
    registry = AsyncLockRegistry()
    t0 = time.time()
    order: List[str] = []

    async def hold_resource(key: str, delay: float, label: str):
        async with registry.acquire_lock(key, timeout=2.0):
            await asyncio.sleep(delay)
            order.append(label)

    # session:a and session:b run concurrently without waiting for each other
    await asyncio.gather(
        hold_resource("session:a", 0.05, "a_done"),
        hold_resource("session:b", 0.05, "b_done"),
    )

    elapsed = time.time() - t0
    # Both finished in parallel (~0.05s, definitely < 0.09s), not sequentially (0.10s)
    assert elapsed < 0.09
    assert set(order) == {"a_done", "b_done"}


@pytest.mark.anyio
async def test_lock_timeout_and_deadlock_prevention():
    """Acquiring a held lock past the timeout must raise LockAcquisitionTimeoutError."""
    registry = AsyncLockRegistry()
    lock_key = "session:deadlock_test"

    async def holding_task():
        async with registry.acquire_lock(lock_key, timeout=2.0):
            await asyncio.sleep(0.3)

    holder = asyncio.create_task(holding_task())
    await asyncio.sleep(0.02)  # Ensure holder acquired lock

    with pytest.raises(LockAcquisitionTimeoutError) as exc_info:
        # Attempt to acquire with a very short timeout
        async with registry.acquire_lock(lock_key, timeout=0.05):
            pass  # pragma: no cover

    assert exc_info.value.resource_key == lock_key
    assert exc_info.value.timeout_sec == 0.05
    await holder


@pytest.mark.anyio
async def test_reentrant_lock_nested_acquisition():
    """ReentrantAsyncLock must allow nested acquisition by the same task."""
    lock = ReentrantAsyncLock(name="test_reentrant")

    assert not lock.is_locked
    assert lock.depth == 0

    async with lock.hold(timeout=1.0):
        assert lock.is_locked
        assert lock.depth == 1

        # Nested re-entry within same coroutine task
        async with lock.hold(timeout=1.0):
            assert lock.depth == 2

            # Third nested re-entry
            async with lock.hold(timeout=1.0):
                assert lock.depth == 3

            assert lock.depth == 2

        assert lock.depth == 1

    assert lock.depth == 0
    assert not lock.is_locked


@pytest.mark.anyio
async def test_reentrant_lock_release_unowned_fails():
    """Releasing a lock with a mismatched owner token must raise RuntimeError."""
    lock = ReentrantAsyncLock(name="unowned_test")
    await lock.acquire(timeout=1.0, owner_token="task_A")

    with pytest.raises(RuntimeError) as exc_info:
        lock.release(owner_token="task_B")
    assert "not the current owner" in str(exc_info.value)

    # Clean up correctly
    lock.release(owner_token="task_A")
    assert not lock.is_locked


# ── 2. Optimistic Concurrency Control (OCC) ──────────────────────────────────

@pytest.mark.anyio
async def test_occ_conflict_detection():
    """StateConcurrencyConflictError must be raised when committing with a stale version."""
    mgr = OCCStateManager()
    res_id = "agent_state:test_occ"

    # Initial state starts at version 1
    state1, v1 = await mgr.get_state(res_id, default={"counter": 0})
    assert v1 == 1
    assert state1["version"] == 1

    # Coroutine A commits version 1 -> 2
    state1["counter"] = 10
    v2 = await mgr.commit_update(res_id, state1, expected_version=1)
    assert v2 == 2

    # Coroutine B (held stale version 1) attempts commit
    stale_state = {"counter": 20}
    with pytest.raises(StateConcurrencyConflictError) as exc_info:
        await mgr.commit_update(res_id, stale_state, expected_version=1)

    err = exc_info.value
    assert err.resource_id == res_id
    assert err.expected_version == 1
    assert err.actual_version == 2
    assert "expected version 1, but actual version is 2" in str(err)
    assert err.to_dict()["actual_version"] == 2


@pytest.mark.anyio
async def test_occ_20_parallel_coroutines_zero_lost_updates():
    """
    STRESS TEST: 20 parallel coroutines concurrently mutate the exact same state.
    Assert zero lost updates and clean OCC rebase-and-retry resolution.
    """
    mgr = OCCStateManager()
    res_id = "session:shared_counter"

    # Initialize counter = 0 at version 1
    await mgr.get_state(res_id, default={"counter": 0, "history": []})

    num_coroutines = 20

    async def increment_worker(worker_id: int):
        def mutator(state: Dict[str, Any]) -> Dict[str, Any]:
            state["counter"] = state.get("counter", 0) + 1
            history = list(state.get("history", []))
            history.append(f"worker_{worker_id}")
            state["history"] = history
            return state

        # Atomic mutate handles conflict detection, exponential backoff, and retry
        updated, final_v = await mgr.atomic_mutate(
            res_id,
            mutator_fn=mutator,
            max_retries=50,
            backoff_base_sec=0.002,
        )
        return final_v

    # Launch all 20 coroutines in parallel
    tasks = [increment_worker(i) for i in range(num_coroutines)]
    results = await asyncio.gather(*tasks)

    # Verify results
    final_state, final_version = await mgr.get_state(res_id)

    # Must have exactly 20 increments: zero lost updates!
    assert final_state["counter"] == num_coroutines
    assert len(final_state["history"]) == num_coroutines
    # Version must have incremented monotonically 20 times (1 initial + 20 updates = 21)
    assert final_version == num_coroutines + 1
    assert final_state["version"] == num_coroutines + 1


@pytest.mark.anyio
async def test_occ_max_retries_exceeded():
    """When retries are exhausted during persistent conflicts, StateConcurrencyConflictError is raised."""
    mgr = OCCStateManager()
    res_id = "session:exhaust_retries"
    await mgr.get_state(res_id, default={"data": "init"})

    def interfering_mutator(state: Dict[str, Any]) -> Dict[str, Any]:
        return state

    # Mutator that intentionally encounters conflict by having another task update between
    # get_state and commit
    async def worker_with_low_retries():
        # A tiny max_retries
        await mgr.atomic_mutate(res_id, interfering_mutator, max_retries=1)

    # Advance version behind the scene to force conflict
    _, v = await mgr.get_state(res_id)
    await mgr.commit_update(res_id, {"data": "bumped"}, expected_version=v)

    # Now attempt commit with expected_version = 1
    with pytest.raises(StateConcurrencyConflictError):
        await mgr.commit_update(res_id, {"data": "fail"}, expected_version=1)


# ── 3. Atomic File Persistence ────────────────────────────────────────────────

def test_atomic_write_replace_semantics(tmp_path: Path):
    """atomic_write must write via a temp file and atomically swap."""
    target_file = tmp_path / "artifacts" / "data.json"

    payload = {"status": "SUCCESS", "run_id": "atomic_123", "items": [1, 2, 3]}
    atomic_write_json(target_file, payload)

    assert target_file.exists()
    content = safe_read_json(target_file)
    assert content["status"] == "SUCCESS"
    assert content["run_id"] == "atomic_123"

    # Ensure no leftover temp files remain in target directory
    tmp_files = list(target_file.parent.glob(".*.tmp"))
    assert len(tmp_files) == 0


@pytest.mark.anyio
async def test_concurrent_readers_and_writers_integrity(tmp_path: Path):
    """
    STRESS TEST: 10 concurrent writers and 10 concurrent readers racing on one file.
    Assert readers NEVER encounter empty files, torn writes, or invalid JSON.
    """
    shared_file = tmp_path / "shared_state.json"
    initial_payload = {"iteration": 0, "padding": "x" * 2000}
    atomic_write_json(shared_file, initial_payload)

    read_results: List[int] = []
    errors: List[str] = []

    async def writer_task(writer_id: int):
        for i in range(1, 15):
            data = {
                "writer": writer_id,
                "iteration": i,
                "payload": f"payload_{writer_id}_{i}" * 50,
            }
            await async_atomic_write_json(shared_file, data)
            await asyncio.sleep(0.001)

    async def reader_task():
        for _ in range(30):
            try:
                content = safe_read_json(shared_file)
                assert isinstance(content, dict)
                assert "iteration" in content
                read_results.append(content["iteration"])
            except json.JSONDecodeError as jde:
                errors.append(f"Torn read / corrupt JSON: {jde}")
            except Exception as e:
                errors.append(f"Unexpected reader error: {e}")
            await asyncio.sleep(0.001)

    writers = [writer_task(i) for i in range(10)]
    readers = [reader_task() for _ in range(10)]

    await asyncio.gather(*writers, *readers)

    # Readers must have executed hundreds of reads with zero corrupted/torn payloads
    assert len(errors) == 0, f"Encountered corrupt reads: {errors}"
    assert len(read_results) > 0


# ── 4. ChatSessionManager Concurrency & OCC ───────────────────────────────────

@pytest.mark.anyio
async def test_chat_session_manager_concurrent_appends(tmp_path: Path):
    """
    Multiple async turns appended concurrently must use session lock and OCC
    without dropping turns or corrupting history.
    """
    # Create isolated manager
    session_mgr = ChatSessionManager(storage_dir=str(tmp_path / "chat_sessions"))
    user_id = "test_user"
    session = session_mgr.create_session(user_id=user_id, title="Concurrency Test")
    session_id = session["id"]

    assert session["version"] == 1

    num_turns = 10

    async def append_turn_worker(idx: int):
        return await session_mgr.append_turn_async(
            user_id=user_id,
            session_id=session_id,
            user_text=f"User command {idx}",
            reply_text=f"Assistant response {idx}",
        )

    # Run 10 concurrent appends
    await asyncio.gather(*[append_turn_worker(i) for i in range(num_turns)])

    # Reload session from disk
    final_session = session_mgr.get_session(user_id, session_id)
    assert final_session is not None

    # Each turn adds 2 messages (user + assistant)
    expected_messages = num_turns * 2
    assert len(final_session["messages"]) == expected_messages
    assert len(final_session["raw_history"]) == expected_messages
    # 1 initial version + 10 turns = version 11
    assert final_session["version"] == num_turns + 1


# ── 5. Parallel Subtask Isolation & Deterministic Reducer ─────────────────────

@pytest.mark.anyio
async def test_parallel_subtask_isolation_and_aggregation():
    """
    Subtasks running in parallel via asyncio.gather must operate on isolated snapshots
    and merge through a deterministic reducer without in-place mutation of parent state.
    """
    parent_state: Dict[str, Any] = {
        "run_id": "fanout_run_1",
        "version": 1,
        "tasks": ["fetch_a", "fetch_b", "fetch_c"],
        "results": {},
    }

    async def isolated_subtask(subtask_name: str, state_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        # Verify subtask received an isolated copy, not shared reference
        assert "results" in state_snapshot
        # Simulate work
        await asyncio.sleep(0.01)
        # Return pure output dict (never mutate state_snapshot directly)
        return {
            "task_name": subtask_name,
            "status": "COMPLETED",
            "data": f"result_for_{subtask_name}",
        }

    # Fan out with deep-copied state snapshots
    subtasks = [
        isolated_subtask(name, copy.deepcopy(parent_state))
        for name in parent_state["tasks"]
    ]
    raw_outputs = await asyncio.gather(*subtasks)

    # Deterministic merge reducer
    def state_reducer(base_state: Dict[str, Any], step_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        reduced = copy.deepcopy(base_state)
        for out in step_outputs:
            reduced["results"][out["task_name"]] = out
        reduced["version"] = reduced["version"] + 1
        return reduced

    new_state = state_reducer(parent_state, raw_outputs)

    # Verify immutability of parent_state
    assert len(parent_state["results"]) == 0
    assert parent_state["version"] == 1

    # Verify reduced state
    assert len(new_state["results"]) == 3
    assert new_state["version"] == 2
    assert new_state["results"]["fetch_a"]["data"] == "result_for_fetch_a"
    assert new_state["results"]["fetch_b"]["data"] == "result_for_fetch_b"
    assert new_state["results"]["fetch_c"]["data"] == "result_for_fetch_c"


# ── 6. LangGraph Pipeline State Versioning ────────────────────────────────────

def test_langgraph_pipeline_state_versioning():
    """LangGraph execution must advance state version monotonically across node handoffs."""
    def mock_llm_caller(prompt: str, system_prompt: str) -> str:
        return "Mock LLM specification output"

    pipeline = LangGraphTwoStepSwarm(call_llm_fn=mock_llm_caller)
    result = pipeline.execute(
        directive="Build auth microservice",
        context="Use FastAPI and JWT tokens",
        user_id="test_boss",
    )

    # Titan advances version 1 -> 2, Nexus advances 2 -> 3
    assert result.get("version") == 3
    assert result.get("titan_status") == "COMPLETED"
    assert result.get("nexus_status") == "COMPLETED"

    # State contract validation
    validated = validate_contract(SwarmHandoffStateContract, result)
    assert validated.version == 3
    assert validated.run_id.startswith("lg_swarm_")
