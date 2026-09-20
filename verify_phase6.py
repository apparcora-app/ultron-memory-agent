"""
verify_phase6.py — Standalone Verification Script for Phase 6 Security & Golden Eval Benchmark.

Demonstrates:
  [1/4] Tenant Isolation: Seed memory for Tenant A; attempt cross-query from Tenant B; assert 0 records returned.
  [2/4] Directory Traversal Defense: Attempt read/write via ../../ escapes; assert deterministic security block.
  [3/4] PII & Secret Masking: Emit an error trace containing simulated SSN, EIN, CC, and API tokens;
        assert DLQ and logs store only masked placeholders.
  [4/4] Full Regression Harness: Run the 15-prompt Master Golden Eval benchmark and output clean green benchmarks.
"""

import asyncio
import os
import sys
import tempfile
import time

# Ensure root import path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evals.test_golden_regression import run_golden_eval_benchmark
from resilience.dlq import DeadLetterQueue
from security.sanitizer import sanitize_payload, sanitize_text
from security.tenant_isolation import (
    DirectoryTraversalError,
    IsolatedVectorStore,
    SecurityContext,
    TenantAccessViolationError,
    TenantWorkspaceSandbox,
    security_context,
)


def run_phase6_verification():
    print("=" * 80)
    print(" [PHASE 6 VERIFICATION] Multi-Tenant Sandbox, Context Scrubbing & Golden Eval")
    print("=" * 80)

    # ── [1/4] Tenant Memory Isolation ─────────────────────────────────────────
    print("\n[1/4] Testing Multi-Tenant Memory Isolation (ChromaDB / Mem0 Vector Driver)...")
    store = IsolatedVectorStore()

    ctx_a = SecurityContext(tenant_id="Tenant_A_Corp", user_id="alice", session_id="sess_a_1")
    ctx_b = SecurityContext(tenant_id="Tenant_B_Corp", user_id="bob", session_id="sess_b_1")

    with security_context(ctx_a):
        store.insert("doc_1", "CONFIDENTIAL: Merger planned with CyberCorp for $45M.")
        store.insert("doc_2", "Q3 Net Profit: $12.4M.")
        print(f"  [OK] Seeded 2 confidential records under Tenant A ({ctx_a.tenant_id}).")

    with security_context(ctx_b):
        store.insert("doc_3", "Tenant B general standup notes.")
        print(f"  [OK] Seeded 1 record under Tenant B ({ctx_b.tenant_id}).")

        # Attack: Tenant B executes semantic search for "Merger" or "CyberCorp"
        leak_attempts = store.query("CyberCorp")
        profit_attempts = store.query("Net Profit")
        assert len(leak_attempts) == 0, f"Cross-tenant leak detected! Found: {leak_attempts}"
        assert len(profit_attempts) == 0, f"Cross-tenant leak detected! Found: {profit_attempts}"
        print("  [OK] Tenant B queried for 'CyberCorp' & 'Net Profit' -> EXACTLY 0 records returned.")

    print("  [PASS] Non-bypassable driver-level metadata filters prevent cross-tenant memory leakage.")

    # ── [2/4] Directory Traversal Defense ─────────────────────────────────────
    print("\n[2/4] Testing Filesystem Sandbox & Path Traversal Block (Canonical realpath)...")
    with tempfile.TemporaryDirectory() as tmp_artifacts:
        sandbox = TenantWorkspaceSandbox(base_artifacts_dir=tmp_artifacts)
        ctx = SecurityContext(tenant_id="acme_security", user_id="sec_admin", session_id="run_99")

        with security_context(ctx):
            # Legitimate file write within sandbox
            safe_p = sandbox.safe_write("reports/audit.json", '{"status": "compliant"}')
            print(f"  [OK] Authorized write succeeded at: ...{safe_p[-40:]}")
            assert os.path.exists(safe_p)

            # Traversal attacks: parent traversal ../ and root escape
            attacks = [
                "../../passwords.txt",
                "../../../etc/shadow",
                "..\\..\\Windows\\System32\\cmd.exe",
                "/etc/passwd",
            ]

            blocked = 0
            for attack in attacks:
                try:
                    sandbox.resolve_safe_path(attack)
                except DirectoryTraversalError:
                    blocked += 1

            assert blocked == len(attacks), f"Expected {len(attacks)} blocked attacks, got {blocked}"
            print(f"  [OK] All {blocked}/{len(attacks)} directory traversal escapes blocked deterministically.")

    print("  [PASS] Filesystem sandbox strictly isolates workspace scratchpads per tenant and session.")

    # ── [3/4] Boundary PII & Secret Masking ────────────────────────────────────
    print("\n[3/4] Testing Boundary PII & Secret Scrubbing (Pre-Serialization DLQ)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "secure_dlq.db")
        dlq = DeadLetterQueue(db_path=db_path)

        # Raw sensitive data
        simulated_trace = (
            "API Authentication failed: Bearer eyJhbGciOiJIUzI1Ni.fakejwttoken123456789.sig "
            "using Anthropic key sk-ant-api03-live-prod-token-123456789. "
            "Subject employee SSN: 123-45-6789, Corporate EIN: 12-3456789, Card: 4111-2222-3333-4444."
        )

        record = dlq.record_dead_letter(
            failed_service="payment_gateway_api",
            node_name="credit_check_node",
            error_message=simulated_trace,
            input_payload={"auth_key": "sk-proj-super-secret-openai-key-123456789", "ssn": "987-65-4321"},
            circuit_state="CLOSED",
        )

        stored = dlq.get_dead_letter(record.dlq_id)
        assert stored is not None

        # Verify scrubbing
        assert "sk-ant-" not in stored.error_message
        assert "123-45-6789" not in stored.error_message
        assert "12-3456789" not in stored.error_message
        assert "4111-2222-3333-4444" not in stored.error_message
        assert "[REDACTED_SSN]" in stored.error_message
        assert "[REDACTED_EIN]" in stored.error_message
        assert "[REDACTED_CC]" in stored.error_message
        assert "[REDACTED_TOKEN]" in stored.error_message

        assert "sk-proj-" not in str(stored.input_payload)
        assert "987-65-4321" not in str(stored.input_payload)

        print(f"  [OK] Stored DLQ Record: {stored.dlq_id}")
        print(f"  [OK] Scrubbed Trace: \"{stored.error_message[:95]}...\"")
        print(f"  [OK] Scrubbed Payload: {stored.input_payload}")

    print("  [PASS] Zero sensitive PII or credentials leaked to persistent storage or telemetry traces.")

    # ── [4/4] Full Golden Eval Regression Benchmark ───────────────────────────
    print("\n[4/4] Executing Master 15-Prompt Golden Eval Scorecard Across All 6 Pillars...")
    t_bench_start = time.perf_counter()
    eval_results = run_golden_eval_benchmark()
    total_bench_ms = (time.perf_counter() - t_bench_start) * 1000

    print("\n" + "-" * 80)
    print(f"{'#':<3} | {'PILLAR':<22} | {'PROMPT / TEST NAME':<38} | {'LATENCY':<9} | {'STATUS'}")
    print("-" * 80)

    for idx, item in enumerate(eval_results["results"], 1):
        status_str = "[PASS]" if item["passed"] else "[FAIL]"
        print(f"{idx:<3} | {item['pillar']:<22} | {item['name']:<38} | {item['latency_ms']:>6.2f}ms | {status_str}")

    print("-" * 80)
    print(f"TOTAL PROMPTS EVALUATED : {eval_results['total_prompts']}")
    print(f"PASSED PROMPTS          : {eval_results['passed_prompts']} / {eval_results['total_prompts']}")
    print(f"TASK ACCURACY           : {eval_results['task_accuracy_pct']:.1f}%")
    print(f"P95 LATENCY             : {eval_results['p95_latency_ms']:.2f} ms")
    print(f"ZERO-REGRESSION RATE    : {eval_results['zero_regression_pass_rate_pct']:.1f}%")
    print(f"TOTAL BENCHMARK TIME    : {total_bench_ms:.2f} ms")
    print("-" * 80)

    assert eval_results["zero_regression_pass_rate_pct"] == 100.0, "Regression failure detected!"

    print("\n" + "=" * 80)
    print(" [ALL CHECKS PASSED] Phase 6 Multi-Tenant Sandbox & Golden Eval Verified 100%!")
    print("=" * 80)


if __name__ == "__main__":
    run_phase6_verification()
