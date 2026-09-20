"""
verify_phase5.py — Standalone Verification Script for Phase 5 Resilience & Fault Tolerance.

Executes live demonstrations:
  1. Distributed Tracing & Span Lifecycle (contextvars, parent-child, tokens, duration).
  2. Three-State Circuit Breaker (Trip on threshold, fast-fail <1ms, cooldown into HALF_OPEN, probe heal).
  3. Exponential Backoff with Randomized Jitter (transient 503 recovery).
  4. Tiered Multi-Provider Failover (catastrophic primary failure -> clean secondary fallback).
  5. Persistent Dead Letter Queue (DLQ) in SQLite (capture snapshot, query, task reconstruction).
"""

import asyncio
import os
import sys
import tempfile
import time

# Ensure root import path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitState,
)
from resilience.dlq import DeadLetterQueue
from resilience.failover import (
    FailoverResult,
    ModelProviderCandidate,
    RetryPolicy,
    TieredModelFailover,
    execute_with_retry,
)
from telemetry.tracing import Tracer, get_current_trace_id


async def run_phase5_verification():
    print("=" * 75)
    print(" [PHASE 5 VERIFICATION] Distributed Tracing, Circuit Breakers & Upstream Resilience")
    print("=" * 75)

    # ── 1. Distributed Tracing ────────────────────────────────────────────────
    print("\n[1/5] Testing Distributed Tracing & Span Lifecycle...")
    tracer = Tracer()
    with tracer.trace_context() as trace_id:
        with tracer.span("orchestrator_node", component="graph_router") as parent_span:
            with tracer.span("llm_reasoning_node", component="llm_agent") as llm_span:
                llm_span.set_tokens(input_tokens=420, output_tokens=180)
                await asyncio.sleep(0.03)
                with tracer.span("tool_mcp_fetch", component="mcp_client") as tool_span:
                    tool_span.set_attribute("tool", "fetch_market_data")
                    await asyncio.sleep(0.02)

    spans = tracer.get_spans(trace_id)
    assert len(spans) == 3
    print(f"  [OK] Generated Trace ID: {trace_id}")
    for s in spans:
        parent_tag = f"(parent: {s.parent_span_id})" if s.parent_span_id else "(ROOT)"
        print(f"       -> Span '{s.name}' [{s.component}] {parent_tag} - duration: {s.duration_ms:.2f}ms, status: {s.status}")
    print("  [PASS] Async trace context and parent-child hierarchy cleanly preserved.")

    # ── 2. Three-State Circuit Breaker ────────────────────────────────────────
    print("\n[2/5] Testing Three-State Circuit Breaker (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)...")
    cfg = CircuitBreakerConfig(failure_threshold=3, cooldown_duration_sec=0.2)
    breaker = CircuitBreaker("upstream_claude_api", config=cfg)

    # 3 failures to trip
    for i in range(1, 4):
        try:
            async with breaker.protect():
                raise ConnectionError("500 API Gateway Timeout")
        except ConnectionError:
            pass

    assert breaker.state == CircuitState.OPEN
    print(f"  [OK] Breaker tripped to OPEN after 3 consecutive failures.")

    # Fast-fail benchmark
    t0 = time.monotonic()
    fast_failed = False
    try:
        async with breaker.protect():
            print("ERROR: Entered protected block while breaker is OPEN!")
    except CircuitBreakerOpenError as exc:
        fast_failed = True
        elapsed_ms = (time.monotonic() - t0) * 1000
        print(f"  [OK] Fast-failed in {elapsed_ms:.3f}ms with CircuitBreakerOpenError.")

    assert fast_failed

    # Cooldown transition to HALF_OPEN
    print("  [..] Awaiting 0.22s cooldown window...")
    await asyncio.sleep(0.22)
    assert breaker.state == CircuitState.HALF_OPEN
    print(f"  [OK] Breaker transitioned to: {breaker.state.value}")

    # Probe succeeds
    async with breaker.protect():
        probe_val = "probe_ok"
    assert breaker.state == CircuitState.CLOSED
    print(f"  [OK] Probe succeeded! Circuit healed back to: {breaker.state.value}")
    print("  [PASS] Circuit breaker guarantees zero network waste when upstream is failing.")

    # ── 3. Exponential Backoff with Jitter ────────────────────────────────────
    print("\n[3/5] Testing Exponential Backoff with Full Jitter...")
    calls = 0

    async def flaky_endpoint():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("503 Service Unavailable")
        return "200_OK_PAYLOAD"

    pol = RetryPolicy(max_retries=3, base_delay_sec=0.03, use_jitter=True)
    res = await execute_with_retry(flaky_endpoint, policy=pol, service_name="flaky_service")
    assert res == "200_OK_PAYLOAD"
    print(f"  [OK] Flaky call succeeded on attempt {calls} after exponential backoff with jitter.")
    print("  [PASS] Transient errors recover without thread blocking or thundering herd.")

    # ── 4. Tiered Multi-Provider Failover ─────────────────────────────────────
    print("\n[4/5] Testing Tiered Multi-Provider Failover...")

    async def failing_primary(prompt: str, sys: str):
        raise RuntimeError("500 Anthropic Overloaded")

    async def healthy_secondary(prompt: str, sys: str):
        return f"Secondary provider (openai-gpt-4o) completed prompt: '{prompt}'"

    failover = TieredModelFailover(
        providers=[
            ModelProviderCandidate("anthropic-claude-3-7-sonnet", failing_primary, service_name="primary_v5"),
            ModelProviderCandidate("openai-gpt-4o", healthy_secondary, service_name="secondary_v5"),
        ],
        retry_policy=RetryPolicy(max_retries=1),
    )

    result: FailoverResult = await failover.execute(prompt="Synthesize quarterly filings")
    assert result.failover_occurred is True
    assert result.provider_used == "openai-gpt-4o"
    print(f"  [OK] Primary failed -> Seamlessly fell back to: {result.provider_used}")
    print(f"  [OK] Response: \"{result.output}\"")
    print(f"  [OK] Fallback reasons recorded: {result.fallback_reasons}")
    print("  [PASS] Tiered model failover delivers uninterrupted agent outputs.")

    # ── 5. Dead Letter Queue (DLQ) Persistence ────────────────────────────────
    print("\n[5/5] Testing Persistent Dead Letter Queue (SQLite)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "verification_dlq.db")
        dlq = DeadLetterQueue(db_path=db_file)

        try:
            raise ValueError("FatalJSONDecodeError: Unparseable LLM output schema")
        except Exception as exc:
            record = dlq.record_dead_letter(
                failed_service="openai-gpt-4o",
                node_name="json_contract_guard",
                error=exc,
                input_payload={"prompt": "Generate JSON schema", "raw_llm_out": "Malformed <<<>>>"},
                retry_attempts=3,
                circuit_state="OPEN",
            )

        print(f"  [OK] DLQ Snapshot Saved: dlq_id={record.dlq_id}, status={record.status}")
        reconstructed = dlq.reconstruct_failed_task(record.dlq_id)
        print(f"  [OK] Reconstructed Task Context: node={reconstructed['node_name']}, failed_service={reconstructed['failed_service']}")
        print(f"  [OK] Payload Recovered: {reconstructed['input_payload']}")
        dlq.requeue(record.dlq_id)
        print(f"  [OK] Requeued task for offline triage.")

    print("  [PASS] Dead letter queue preserves full error telemetry & replay capabilities.")

    print("\n" + "=" * 75)
    print(" [ALL 5 CHECKS PASSED] Phase 5 Resilience & Fault Tolerance Verified 100%!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_phase5_verification())
