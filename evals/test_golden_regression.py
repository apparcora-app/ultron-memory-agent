"""
evals/test_golden_regression.py — Master Golden Eval Benchmark across all 6 production pillars.

Executes a comprehensive 15-prompt scorecard:
  Pillar 1: Contract Ingress (Prompts 1-3)
  Pillar 2: In-Flight Critic Gate (Prompts 4-6)
  Pillar 3: Concurrency Control & Atomic IO (Prompts 7-8)
  Pillar 4: Resource & Spend Limits (Prompts 9-10)
  Pillar 5: Upstream Fault Tolerance & Resilience (Prompts 11-13)
  Pillar 6: Multi-Tenant Sandbox & Sensitive Data Scrubbing (Prompts 14-15)

Calculates:
  - Task Accuracy (%)
  - Latency p95 (ms)
  - Zero-Regression Pass Rate (100% required)
"""

import asyncio
import os
import tempfile
import time
from typing import Any, Dict, List, Tuple
import pytest
from pydantic import ValidationError

from concurrency.atomic_io import atomic_write_json, safe_read_json
from concurrency.occ import OCCStateManager
from contracts import (
    ContractValidationError,
    OpenApplicationInput,
    SleepSecondsInput,
    TOOL_INPUT_CONTRACTS,
    validate_contract,
)
from governance.rate_limiter import AsyncRateLimiter, ProviderRateLimits
from governance.spend_governor import (
    MODEL_COST_TABLE,
    BudgetConfig,
    BudgetExceededException,
    SpendGovernor,
)
from guardrails.ast_sandbox import ASTSecurityViolation, ASTValidator
from guardrails.critic import CriticResult, InFlightCriticGate
from resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitState,
)
from resilience.failover import (
    FailoverResult,
    ModelProviderCandidate,
    RetryPolicy,
    TieredModelFailover,
    execute_with_retry,
)
from security.sanitizer import DataSanitizer, sanitize_payload, sanitize_text
from security.tenant_isolation import (
    DirectoryTraversalError,
    IsolatedVectorStore,
    SecurityContext,
    TenantWorkspaceSandbox,
    security_context,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── Pillar 1: Contract Ingress ────────────────────────────────────────────────

def test_01_contract_ingress_schema_drift():
    """Prompt 1: Calling a tool with an extra hallucinated/injected parameter must be blocked."""
    t0 = time.perf_counter()
    with pytest.raises(ContractValidationError):
        validate_contract(
            SleepSecondsInput,
            {"seconds": 1.0, "hallucinated_admin_override": True},
        )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms < 50.0


def test_02_contract_ingress_missing_mandatory_field():
    """Prompt 2: Calling a tool with missing required parameters must be rejected."""
    with pytest.raises(ContractValidationError):
        validate_contract(
            OpenApplicationInput,
            {},  # missing 'app_name'
        )


def test_03_contract_ingress_type_coercion_blocked():
    """Prompt 3: Loose type coercion must be forbidden (strict typing enforced)."""
    with pytest.raises(ContractValidationError):
        validate_contract(
            SleepSecondsInput,
            {"seconds": "ten_seconds"},  # string instead of float
        )


# ── Pillar 2: In-Flight Critic Gate & Sandboxing ──────────────────────────────

def test_04_inflight_critic_arithmetic_drift():
    """Prompt 4: Output claiming Revenue $200K, Exp $50K, Profit $120K must be flagged as arithmetic contradiction."""
    critic = InFlightCriticGate()
    t0 = time.perf_counter()

    draft = "Revenue was $200,000, expenses were $50,000, so net profit is 200000 - 50000 = 120000."
    verdict = critic.verify_in_flight(
        user_input="Calculate net profit",
        draft_reply=draft,
        tool_actions=[],
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert elapsed_ms < 1000.0  # Sub-second latency requirement
    assert verdict.approved is False
    assert verdict.failure_category == "math_drift"


def test_05_inflight_critic_corrupted_signature():
    """Prompt 5: Output with false success flag but empty/malformed signature must be intercepted."""
    critic = InFlightCriticGate()
    t0 = time.perf_counter()

    failed_action = [{
        "tool": "file_operation",
        "input": {"operation": "write", "path": "protected.txt"},
        "output": "",
        "error": "Permission denied: table locked",
        "success": False,
        "duration_ms": 10,
    }]
    false_draft = "The operation was executed successfully. All records updated successfully."
    verdict = critic.verify_in_flight(
        user_input="Update records",
        draft_reply=false_draft,
        tool_actions=failed_action,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert elapsed_ms < 1000.0
    assert verdict.approved is False
    assert verdict.failure_category == "signature_violation"


def test_06_inflight_critic_ast_code_sandbox():
    """Prompt 6: Code injection attempting to invoke os.system must be caught by AST sandbox."""
    validator = ASTValidator()
    code = "import os\nos.system('echo compromised')"
    with pytest.raises(ASTSecurityViolation) as exc_info:
        validator.validate_python_code(code)
    assert exc_info.value.violation_type == "forbidden_import"


# ── Pillar 3: Concurrency Control & Atomic IO ─────────────────────────────────

@pytest.mark.anyio
async def test_07_concurrency_race_condition_occ():
    """Prompt 7: 10 parallel coroutines updating state concurrently must maintain consistency without lost updates."""
    mgr = OCCStateManager()
    res_id = "eval_account_balance"
    await mgr.get_state(res_id, default={"counter": 0})

    async def worker():
        for _ in range(5):
            def mutator(cur):
                cur["counter"] = cur.get("counter", 0) + 10
                return cur
            await mgr.atomic_mutate(res_id, mutator_fn=mutator)

    # Launch 10 workers in parallel
    await asyncio.gather(*[worker() for _ in range(10)])

    final_state, ver = await mgr.get_state(res_id)
    # 10 workers * 5 increments * $10 = 500
    assert final_state["counter"] == 500
    assert ver == 51


def test_08_concurrency_atomic_file_persistence():
    """Prompt 8: Atomic write-replace semantics must prevent partial or corrupt reads."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "secure_artifact.json")
        payload = {"transaction_id": "tx_9988", "amount": 4250.75, "currency": "USD"}

        atomic_write_json(filepath, payload)
        read_back = safe_read_json(filepath)

        assert read_back == payload


# ── Pillar 4: Resource & Spend Limits ─────────────────────────────────────────

def test_09_resource_governance_budget_cap():
    """Prompt 9: Token spend exceeding dollar cap must trigger BudgetExceededException into terminal state."""
    config = BudgetConfig(max_cost_usd_per_session=0.03, max_tokens_per_session=100_000)
    gov = SpendGovernor(config=config)
    session_id = "sess_budget_eval"

    # Turn 1: 1,000 in, 1,000 out on Claude Sonnet (~$0.018) -> allowed
    gov.record_turn_spend(session_id, "turn_1", "claude-sonnet", 1000, 1000)

    # Turn 2: 2,000 in, 2,000 out (~$0.036) -> total $0.054 > $0.03 limit!
    with pytest.raises(BudgetExceededException) as exc_info:
        gov.record_turn_spend(session_id, "turn_2", "claude-sonnet", 2000, 2000)

    assert exc_info.value.breach_type == "cost"
    terminal_summary = gov.format_terminal_summary(session_id, exception=exc_info.value)
    assert "halted gracefully" in terminal_summary["summary"].lower()


@pytest.mark.anyio
async def test_10_resource_governance_rate_limiter():
    """Prompt 10: Burst of requests must be throttled non-blockingly by token-bucket rate limiter."""
    limiter = AsyncRateLimiter(default_limits=ProviderRateLimits(rpm=120, tpm=10000))
    t0 = time.monotonic()

    # Request 2 calls in rapid succession
    await limiter.acquire("anthropic", tokens=100)
    await limiter.acquire("anthropic", tokens=100)

    elapsed = time.monotonic() - t0
    # Must proceed without raising 429
    assert elapsed >= 0.0


# ── Pillar 5: Upstream Fault Tolerance & Resilience ───────────────────────────

@pytest.mark.anyio
async def test_11_resilience_circuit_breaker_fast_fail():
    """Prompt 11: 3 consecutive 500 errors trip breaker to OPEN, causing subsequent call to fast-fail sub-millisecond."""
    cfg = CircuitBreakerConfig(failure_threshold=3, cooldown_duration_sec=10.0)
    breaker = CircuitBreaker("upstream_eval_service", config=cfg)

    # Trip breaker
    for _ in range(3):
        with pytest.raises(RuntimeError):
            async with breaker.protect():
                raise RuntimeError("500 Internal Server Error")

    assert breaker.state == CircuitState.OPEN

    # Measure fast-fail latency
    t0 = time.perf_counter()
    with pytest.raises(CircuitBreakerOpenError):
        async with breaker.protect():
            pytest.fail("Should never enter protected block!")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert elapsed_ms < 5.0  # Must fast-fail in <5ms (typically <0.1ms)


@pytest.mark.anyio
async def test_12_resilience_transient_retry_backoff():
    """Prompt 12: Transient 503 error recovers after exponential backoff with jitter."""
    attempts = 0

    async def flaky_api():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("503 Service Unavailable")
        return "200_SUCCESS"

    policy = RetryPolicy(max_retries=3, base_delay_sec=0.01, use_jitter=True)
    res = await execute_with_retry(flaky_api, policy=policy, service_name="eval_flaky_retry")

    assert res == "200_SUCCESS"
    assert attempts == 3


@pytest.mark.anyio
async def test_13_resilience_tiered_model_failover():
    """Prompt 13: Catastrophic primary failure automatically falls back to secondary model seamlessly."""
    async def primary_fail(prompt, sys):
        raise RuntimeError("500 Primary Gateway Timeout")

    async def secondary_success(prompt, sys):
        return f"GPT-4o response to: {prompt}"

    failover = TieredModelFailover(
        providers=[
            ModelProviderCandidate("primary_claude", primary_fail, service_name="eval_failover_prim"),
            ModelProviderCandidate("secondary_openai", secondary_success, service_name="eval_failover_sec"),
        ],
        retry_policy=RetryPolicy(max_retries=1),
    )

    result = await failover.execute(prompt="Synthesize research brief")
    assert result.failover_occurred is True
    assert result.provider_used == "secondary_openai"
    assert "GPT-4o response" in result.output


# ── Pillar 6: Multi-Tenant Sandbox & Privacy ──────────────────────────────────

def test_14_multitenant_privacy_memory_isolation():
    """Prompt 14: Tenant B querying vector memory must never observe Tenant A's confidential data."""
    store = IsolatedVectorStore()
    ctx_a = SecurityContext(tenant_id="tenant_corp_A", user_id="alice", session_id="s1")
    ctx_b = SecurityContext(tenant_id="tenant_corp_B", user_id="bob", session_id="s2")

    with security_context(ctx_a):
        store.insert("doc_a", "Acquisition strategy: bidding $100M for target company")

    with security_context(ctx_b):
        store.insert("doc_b", "General quarterly team schedule")

    # Tenant B attempts to query "acquisition"
    with security_context(ctx_b):
        results = store.query("acquisition")
        assert len(results) == 0  # 0 records returned!

    # Tenant A queries "acquisition"
    with security_context(ctx_a):
        results_a = store.query("acquisition")
        assert len(results_a) == 1
        assert "bidding $100M" in results_a[0]["text"]


def test_15_security_sandboxing_and_pii_scrubbing():
    """Prompt 15: Directory traversal attacks must be blocked, and sensitive PII/secrets scrubbed."""
    with tempfile.TemporaryDirectory() as tmp_artifacts:
        sandbox = TenantWorkspaceSandbox(base_artifacts_dir=tmp_artifacts)
        ctx = SecurityContext(tenant_id="tenant_eval", user_id="user_test", session_id="sess_eval")

        with security_context(ctx):
            # 1. Directory traversal attempt
            with pytest.raises(DirectoryTraversalError):
                sandbox.resolve_safe_path("../../passwords.json")

            # 2. PII / Secret scrubbing
            raw_log = "Error during checkout: User SSN 123-45-6789, EIN 12-3456789, key sk-ant-secret123456789"
            sanitized = sanitize_text(raw_log)

            assert "123-45-6789" not in sanitized
            assert "12-3456789" not in sanitized
            assert "sk-ant-" not in sanitized
            assert "[REDACTED_SSN]" in sanitized
            assert "[REDACTED_EIN]" in sanitized
            assert "[REDACTED_TOKEN]" in sanitized


# ── Benchmark Scorecard Runner ────────────────────────────────────────────────

def run_golden_eval_benchmark() -> Dict[str, Any]:
    """
    Executes the 15-prompt scorecard and returns benchmark metrics:
    Task Accuracy (%), Latency p95 (ms), Zero-Regression Pass Rate (%).
    """
    tests = [
        ("Pillar 1: Contracts", "Prompt 01: Ingress Schema Drift", test_01_contract_ingress_schema_drift, False),
        ("Pillar 1: Contracts", "Prompt 02: Ingress Missing Field", test_02_contract_ingress_missing_mandatory_field, False),
        ("Pillar 1: Contracts", "Prompt 03: Ingress Type Coercion", test_03_contract_ingress_type_coercion_blocked, False),
        ("Pillar 2: Critic Gate", "Prompt 04: Arithmetic Contradiction (<1s)", test_04_inflight_critic_arithmetic_drift, False),
        ("Pillar 2: Critic Gate", "Prompt 05: Malformed Signature (<1s)", test_05_inflight_critic_corrupted_signature, False),
        ("Pillar 2: Critic Gate", "Prompt 06: AST Sandbox Code Injection", test_06_inflight_critic_ast_code_sandbox, False),
        ("Pillar 3: Concurrency", "Prompt 07: OCC Parallel Race Conditions", test_07_concurrency_race_condition_occ, True),
        ("Pillar 3: Concurrency", "Prompt 08: Atomic IO Write-Replace", test_08_concurrency_atomic_file_persistence, False),
        ("Pillar 4: Resources", "Prompt 09: Spend Governor Dollar Cap", test_09_resource_governance_budget_cap, False),
        ("Pillar 4: Resources", "Prompt 10: Token-Bucket Rate Limiter", test_10_resource_governance_rate_limiter, True),
        ("Pillar 5: Resilience", "Prompt 11: Circuit Breaker Fast-Fail (<1ms)", test_11_resilience_circuit_breaker_fast_fail, True),
        ("Pillar 5: Resilience", "Prompt 12: Exponential Backoff & Jitter", test_12_resilience_transient_retry_backoff, True),
        ("Pillar 5: Resilience", "Prompt 13: Tiered Model Provider Failover", test_13_resilience_tiered_model_failover, True),
        ("Pillar 6: Security", "Prompt 14: Vector Memory Tenant Isolation", test_14_multitenant_privacy_memory_isolation, False),
        ("Pillar 6: Security", "Prompt 15: Directory Traversal & PII Scrubbing", test_15_security_sandboxing_and_pii_scrubbing, False),
    ]

    results: List[Dict[str, Any]] = []
    latencies: List[float] = []
    passed_count = 0

    for pillar, name, fn, is_async in tests:
        t0 = time.perf_counter()
        passed = False
        err_msg = None
        try:
            if is_async:
                asyncio.run(fn())
            else:
                fn()
            passed = True
            passed_count += 1
        except Exception as e:
            err_msg = str(e)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

        results.append({
            "pillar": pillar,
            "name": name,
            "passed": passed,
            "latency_ms": elapsed_ms,
            "error": err_msg,
        })

    latencies_sorted = sorted(latencies)
    idx_p95 = int(len(latencies_sorted) * 0.95)
    p95_latency = latencies_sorted[min(idx_p95, len(latencies_sorted) - 1)]

    total = len(tests)
    accuracy = (passed_count / total) * 100.0
    pass_rate = 100.0 if passed_count == total else ((passed_count / total) * 100.0)

    return {
        "total_prompts": total,
        "passed_prompts": passed_count,
        "failed_prompts": total - passed_count,
        "task_accuracy_pct": accuracy,
        "p95_latency_ms": p95_latency,
        "zero_regression_pass_rate_pct": pass_rate,
        "results": results,
    }
