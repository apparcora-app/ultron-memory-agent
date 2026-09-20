"""
tests/test_phase5_resilience.py — Comprehensive Test Suite for Phase 5 Resilience.

Validates:
  1. Distributed trace propagation (contextvars, parent-child spans, parallel coroutines).
  2. Three-state circuit breaker (CLOSED -> OPEN -> HALF_OPEN -> CLOSED / OPEN, fast-fail <1ms).
  3. Exponential backoff with jitter on transient HTTP 429/500/503 errors.
  4. Tiered model provider failover with seamless state recovery and telemetry audit logging.
  5. Persistent Dead Letter Queue (DLQ) in SQLite with task reconstruction and replay helpers.
"""

import asyncio
import os
import tempfile
import time
import pytest

from resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
    CircuitState,
    default_breaker_registry,
)
from resilience.dlq import DeadLetterQueue, DeadLetterRecord
from resilience.failover import (
    FailoverResult,
    ModelProviderCandidate,
    RetryPolicy,
    TieredModelFailover,
    execute_with_retry,
    is_transient_error,
)
from telemetry.tracing import (
    Tracer,
    get_current_span_id,
    get_current_trace_id,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── 1. Trace Context & Span Lifecycle Tests ───────────────────────────────────

@pytest.mark.anyio
async def test_distributed_trace_context_propagation():
    tracer = Tracer()

    with tracer.trace_context("test_trace_1234") as tid:
        assert get_current_trace_id() == "test_trace_1234"

        with tracer.span("root_orchestrator", component="orchestrator") as root_span:
            root_id = root_span.span_id
            assert root_span.trace_id == "test_trace_1234"
            assert root_span.parent_span_id is None

            with tracer.span("child_agent_node", component="agent") as child_span:
                assert child_span.trace_id == "test_trace_1234"
                assert child_span.parent_span_id == root_id
                child_span.set_tokens(input_tokens=150, output_tokens=50)

                with tracer.span("grandchild_tool_exec", component="tools") as tool_span:
                    assert tool_span.trace_id == "test_trace_1234"
                    assert tool_span.parent_span_id == child_span.span_id
                    tool_span.set_attribute("tool_name", "sql_query")

    spans = tracer.get_spans("test_trace_1234")
    assert len(spans) == 3

    tool_s = next(s for s in spans if s.name == "grandchild_tool_exec")
    child_s = next(s for s in spans if s.name == "child_agent_node")
    root_s = next(s for s in spans if s.name == "root_orchestrator")

    assert tool_s.status == "OK"
    assert tool_s.attributes["tool_name"] == "sql_query"
    assert child_s.input_tokens == 150
    assert child_s.output_tokens == 50
    assert root_s.parent_span_id is None
    assert root_s.duration_ms >= 0.0


@pytest.mark.anyio
async def test_distributed_trace_across_parallel_tasks():
    tracer = Tracer()

    async def worker_task(worker_id: int, expected_trace_id: str):
        async with tracer.async_span(f"worker_{worker_id}", component="parallel_worker") as span:
            assert get_current_trace_id() == expected_trace_id
            await asyncio.sleep(0.02)
            span.set_attribute("worker_id", worker_id)
            return worker_id * 10

    with tracer.trace_context("shared_trace_parallel") as shared_tid:
        results = await asyncio.gather(
            worker_task(1, shared_tid),
            worker_task(2, shared_tid),
            worker_task(3, shared_tid),
        )

    assert results == [10, 20, 30]
    spans = tracer.get_spans("shared_trace_parallel")
    assert len(spans) == 3
    for s in spans:
        assert s.trace_id == "shared_trace_parallel"
        assert s.status == "OK"


# ── 2. Three-State Circuit Breaker Tests ──────────────────────────────────────

@pytest.mark.anyio
async def test_circuit_breaker_trip_and_cooldown_recovery():
    cfg = CircuitBreakerConfig(failure_threshold=3, cooldown_duration_sec=0.15)
    breaker = CircuitBreaker("mock_upstream_api", config=cfg)

    assert breaker.state == CircuitState.CLOSED

    # Trigger 3 consecutive failures
    for i in range(3):
        with pytest.raises(RuntimeError):
            async with breaker.protect():
                raise RuntimeError(f"500 Internal Server Error {i}")

    # Breaker should now be OPEN
    assert breaker.state == CircuitState.OPEN
    assert breaker.consecutive_failures == 3

    # Fast-fail test: Attempting call when OPEN immediately raises CircuitBreakerOpenError without execution
    t_start = time.monotonic()
    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        async with breaker.protect():
            # This block should never be entered!
            pytest.fail("Protected block executed while circuit breaker was OPEN!")

    t_elapsed = time.monotonic() - t_start
    assert t_elapsed < 0.01  # Must fast-fail in sub-10ms
    assert exc_info.value.service_name == "mock_upstream_api"
    assert exc_info.value.consecutive_failures == 3

    # Wait for cooldown to expire
    await asyncio.sleep(0.18)

    # State dynamically transitions to HALF_OPEN
    assert breaker.state == CircuitState.HALF_OPEN

    # Execute successful probe
    async with breaker.protect():
        probe_result = "probe_success"

    assert probe_result == "probe_success"
    # Circuit should now be healed to CLOSED
    assert breaker.state == CircuitState.CLOSED
    assert breaker.consecutive_failures == 0


@pytest.mark.anyio
async def test_circuit_breaker_probe_failure_trips_back_to_open():
    cfg = CircuitBreakerConfig(failure_threshold=2, cooldown_duration_sec=0.1)
    breaker = CircuitBreaker("probe_fail_service", config=cfg)

    for _ in range(2):
        with pytest.raises(Exception):
            async with breaker.protect():
                raise ConnectionResetError("Connection reset")

    assert breaker.state == CircuitState.OPEN

    await asyncio.sleep(0.12)
    assert breaker.state == CircuitState.HALF_OPEN

    # Probe fails
    with pytest.raises(ConnectionResetError):
        async with breaker.protect():
            raise ConnectionResetError("Probe failed")

    # Should immediately trip back to OPEN
    assert breaker.state == CircuitState.OPEN


# ── 3. Exponential Backoff with Jitter Tests ─────────────────────────────────

@pytest.mark.anyio
async def test_transient_retry_with_backoff():
    policy = RetryPolicy(max_retries=3, base_delay_sec=0.02, multiplier=1.5, use_jitter=True)
    attempts = 0

    async def unstable_network_call():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("503 Service Unavailable")
        return "success_payload"

    result = await execute_with_retry(
        call_fn=unstable_network_call,
        policy=policy,
        service_name="test_retry_service",
    )

    assert result == "success_payload"
    assert attempts == 3


@pytest.mark.anyio
async def test_non_transient_error_fails_immediately_without_retry():
    policy = RetryPolicy(max_retries=3, base_delay_sec=0.05)
    attempts = 0

    async def invalid_request_call():
        nonlocal attempts
        attempts += 1
        raise ValueError("Invalid schema: missing field 'name'")

    with pytest.raises(ValueError, match="Invalid schema"):
        await execute_with_retry(
            call_fn=invalid_request_call,
            policy=policy,
            service_name="non_transient_test",
        )

    # Permanent error must fail on attempt 1
    assert attempts == 1


# ── 4. Tiered Model Failover Tests ───────────────────────────────────────────

@pytest.mark.anyio
async def test_tiered_failover_automatic_fallback():
    class MockTelemetry:
        def __init__(self):
            self.events = []

        def log_event(self, user_id, event_type, module_id, details):
            self.events.append({
                "user_id": user_id,
                "event_type": event_type,
                "module_id": module_id,
                "details": details,
            })

    telemetry = MockTelemetry()

    # Primary provider fails with 500
    async def primary_caller(prompt: str, sys: str):
        raise RuntimeError("500 Claude API Overloaded")

    # Secondary provider succeeds
    async def secondary_caller(prompt: str, sys: str):
        return f"Fallback GPT-4o response to: {prompt}"

    providers = [
        ModelProviderCandidate(name="anthropic-claude-3-7-sonnet", caller=primary_caller, service_name="anthropic_failover_test"),
        ModelProviderCandidate(name="openai-gpt-4o", caller=secondary_caller, service_name="openai_failover_test"),
    ]

    policy = RetryPolicy(max_retries=2, base_delay_sec=0.01)
    failover_engine = TieredModelFailover(
        providers=providers,
        retry_policy=policy,
        telemetry_engine=telemetry,
    )

    result = await failover_engine.execute(
        prompt="Analyze revenue trend",
        user_id="analyst_1",
    )

    assert isinstance(result, FailoverResult)
    assert result.failover_occurred is True
    assert result.provider_used == "openai-gpt-4o"
    assert "Fallback GPT-4o response to: Analyze revenue trend" in result.output
    assert len(telemetry.events) == 1
    assert telemetry.events[0]["event_type"] == "PROVIDER_FAILOVER"
    assert telemetry.events[0]["details"]["primary_provider"] == "anthropic-claude-3-7-sonnet"
    assert telemetry.events[0]["details"]["fallback_provider"] == "openai-gpt-4o"


@pytest.mark.anyio
async def test_tiered_failover_skips_open_circuit_breaker():
    primary_breaker = default_breaker_registry.get_breaker("primary_model_fast_fail")
    primary_breaker.reset()
    # Manually trip to OPEN
    primary_breaker.record_failure(RuntimeError("Outage"))
    primary_breaker.record_failure(RuntimeError("Outage"))
    primary_breaker.record_failure(RuntimeError("Outage"))
    assert primary_breaker.state == CircuitState.OPEN

    primary_invoked = False

    async def primary_caller(prompt: str, sys: str):
        nonlocal primary_invoked
        primary_invoked = True
        return "primary_output"

    async def secondary_caller(prompt: str, sys: str):
        return "secondary_output"

    providers = [
        ModelProviderCandidate(name="primary_model", caller=primary_caller, service_name="primary_model_fast_fail"),
        ModelProviderCandidate(name="secondary_model", caller=secondary_caller, service_name="secondary_model_fast_fail"),
    ]

    failover_engine = TieredModelFailover(
        providers=providers,
        retry_policy=RetryPolicy(max_retries=1),
    )

    result = await failover_engine.execute(prompt="Hello")

    assert result.provider_used == "secondary_model"
    assert result.output == "secondary_output"
    assert primary_invoked is False  # Never called because circuit was OPEN


# ── 5. Persistent Dead Letter Queue (DLQ) Tests ──────────────────────────────

def test_dead_letter_queue_persistence_and_replay():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_dlq.db")
        dlq = DeadLetterQueue(db_path=db_path)

        tracer = Tracer()
        with tracer.trace_context("trace_dlq_test_999"):
            # Record an unrecoverable failure snapshot
            try:
                raise ValueError("JSONSchemaValidationError: field 'account_id' is required")
            except Exception as exc:
                record = dlq.record_dead_letter(
                    failed_service="gemini-1.5-pro",
                    node_name="json_extractor_node",
                    error=exc,
                    input_payload={"raw_response": "{'broken': 1}", "expected_schema": "AccountInfo"},
                    retry_attempts=3,
                    circuit_state="OPEN",
                )

        assert record.dlq_id is not None
        assert record.trace_id == "trace_dlq_test_999"
        assert record.failed_service == "gemini-1.5-pro"
        assert record.error_type == "ValueError"
        assert "JSONSchemaValidationError" in record.error_message
        assert record.status == "PENDING"

        # List dead letters
        items = dlq.list_dead_letters(limit=10)
        assert len(items) == 1
        assert items[0].dlq_id == record.dlq_id

        # Reconstruct failed task for replay
        reconstructed = dlq.reconstruct_failed_task(record.dlq_id)
        assert reconstructed["dlq_id"] == record.dlq_id
        assert reconstructed["trace_id"] == "trace_dlq_test_999"
        assert reconstructed["node_name"] == "json_extractor_node"
        assert reconstructed["can_reexecute"] is True
        assert reconstructed["input_payload"]["expected_schema"] == "AccountInfo"

        # Requeue task
        requeued = dlq.requeue(record.dlq_id)
        assert requeued is True
        updated = dlq.get_dead_letter(record.dlq_id)
        assert updated.status == "REQUEUED"

        # Purge
        deleted = dlq.purge()
        assert deleted == 1
        assert len(dlq.list_dead_letters()) == 0
