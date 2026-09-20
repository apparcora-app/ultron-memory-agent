"""
tests/test_phase2_inflight.py — Phase 2 Test Suite: In-Flight Critic Gates & Verification Guardrails.

Covers:
  1. In-flight critic gate mathematical consistency detection (arithmetic drift rejection).
  2. In-flight critic gate output signature fidelity & false-success rejection.
  3. In-flight critic gate sub-second latency verification (<1.0s target).
  4. Single-retry self-correction loop resolution.
  5. AST code execution sandboxing (blocks os, subprocess, eval, exec, unauthorized writes).
  6. AST validator whitelisting of safe scientific & standard modules.
  7. Execution boundary cap enforcement (hard recursion limit = 5 iterations).
  8. Timeout middleware (aborts stalled async operations).
  9. ToolExecutor integration tests with AST sandbox & timeout middleware.
"""

import asyncio
import sys
import time
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest

from guardrails.ast_sandbox import (
    ASTSecurityViolation,
    ASTValidator,
    DEFAULT_SAFE_MODULES,
    DANGEROUS_MODULES,
)
from guardrails.critic import (
    CriticResult,
    InFlightCriticGate,
)
from guardrails.limits import (
    ExecutionLimitExceeded,
    RecursionLimiter,
    dispatch_with_timeout,
    MAX_RECURSION_LIMIT,
    DEFAULT_TOOL_TIMEOUT_SEC,
)
from sandbox import Sandbox, SandboxConfig
from tool_definitions import ToolExecutor


# ── 1. In-Flight Critic: Mathematical Consistency & Contradictions ──────────

def test_critic_flags_mathematical_contradiction():
    """Critic must intercept arithmetic drift and contradictory figures fail-fast."""
    critic = InFlightCriticGate()

    # Case A: Explicit addition drift (125 + 250 != 450)
    draft_with_math_error = (
        "We reviewed the Q3 financial records. The base allocation was $125k and bonus was $250k. "
        "Total expenditure: 125 + 250 = 450k."
    )
    result = critic.verify_in_flight(
        user_input="Calculate total expenditure",
        draft_reply=draft_with_math_error,
        tool_actions=[{"tool": "file_operation", "success": True, "output": "125, 250"}],
    )
    assert result.approved is False
    assert result.failure_category == "math_drift"
    assert result.flaw_severity == "critical"
    assert "Mathematical contradiction" in result.critique

    # Case B: Subtraction drift (100 - 30 != 80)
    draft_sub_error = "Initial balance was 100, deducted 30, remaining: 100 - 30 = 80 units."
    res_sub = critic.verify_in_flight(
        user_input="Check balance",
        draft_reply=draft_sub_error,
        tool_actions=[],
    )
    assert res_sub.approved is False
    assert res_sub.failure_category == "math_drift"

    # Case C: Multiplication drift (12 * 12 != 140)
    draft_mul_error = "The calculated area is 12 * 12 = 140 sq meters."
    res_mul = critic.verify_in_flight(
        user_input="Compute area",
        draft_reply=draft_mul_error,
        tool_actions=[],
    )
    assert res_mul.approved is False
    assert res_mul.failure_category == "math_drift"


# ── 2. In-Flight Critic: Output Signature Fidelity ────────────────────────────

def test_critic_flags_malformed_signature_and_false_success():
    """Critic must reject drafts that claim success when underlying tools failed."""
    critic = InFlightCriticGate()

    # Tool failed with permission error, but draft claims completed successfully
    failed_tool_action = [{
        "tool": "file_operation",
        "input": {"operation": "write", "path": "protected.txt"},
        "output": "",
        "error": "Permission denied: access to protected file blocked",
        "success": False,
        "duration_ms": 12,
    }]
    false_success_draft = (
        "The operation was executed successfully. All files have been updated successfully in production."
    )

    verdict = critic.verify_in_flight(
        user_input="Write protected file",
        draft_reply=false_success_draft,
        tool_actions=failed_tool_action,
    )
    assert verdict.approved is False
    assert verdict.failure_category == "signature_violation"
    assert "failed with error" in verdict.critique


# ── 3. In-Flight Critic: Sub-Second Latency & Valid Passage ───────────────────

def test_critic_allows_valid_output_under_latency_budget():
    """Valid replies must pass verification cleanly with latency < 1.0s (sub-second target)."""
    critic = InFlightCriticGate(latency_budget_sec=1.0)

    valid_tool_actions = [{
        "tool": "run_python",
        "input": {"code": "print(2 + 2)"},
        "output": "4",
        "error": None,
        "success": True,
        "duration_ms": 45,
    }]
    valid_draft = (
        "The calculated value from the Python script is 4. Here is the verified breakdown: 2 + 2 = 4."
    )

    t0 = time.perf_counter()
    verdict = critic.verify_in_flight(
        user_input="Calculate 2 + 2",
        draft_reply=valid_draft,
        tool_actions=valid_tool_actions,
    )
    elapsed = time.perf_counter() - t0

    assert verdict.approved is True
    assert verdict.failure_category == "none"
    assert verdict.flaw_severity == "none"
    # Must comfortably meet the <1.0s sub-second requirement
    assert elapsed < 1.0, f"Critic gate exceeded sub-second latency target: {elapsed:.3f}s"


# ── 4. Single-Retry Self-Correction Loop ──────────────────────────────────────

def test_critic_self_correction_single_retry():
    """Critic must trigger exactly one self-correction pass and return the resolved response."""
    critic = InFlightCriticGate()

    initial_draft = "Total items: 10 + 20 = 50."
    tool_actions = [{"tool": "run_python", "success": True, "output": "30"}]

    call_count = 0

    async def mock_correction_generator(prompt: str) -> str:
        nonlocal call_count
        call_count += 1
        assert "IN-FLIGHT CRITIC REJECTION TRACE" in prompt
        assert "math_drift" in prompt
        # Return corrected output on the retry
        return "Total items: 10 + 20 = 30."

    async def _run():
        final_text, final_verdict = await critic.execute_with_self_correction(
            draft_generator=mock_correction_generator,
            user_input="Sum 10 and 20",
            initial_draft=initial_draft,
            tool_actions=tool_actions,
        )
        assert call_count == 1, "Self-correction must trigger exactly once."
        assert final_verdict.approved is True
        assert final_text == "Total items: 10 + 20 = 30."

    asyncio.run(_run())


# ── 5. AST Sandboxing: Blacklisted Imports & Dangerous Builtins ───────────────

@pytest.mark.parametrize("dangerous_code,expected_violation", [
    ("import os\nprint(os.getcwd())", "forbidden_import"),
    ("import subprocess\nsubprocess.Popen(['ls'])", "forbidden_import"),
    ("from subprocess import Popen", "forbidden_import_from"),
    ("import sys\nsys.exit(1)", "forbidden_import"),
    ("import socket\ns = socket.socket()", "forbidden_import"),
    ("import shutil\nshutil.rmtree('/')", "forbidden_import"),
    ("import ctypes", "forbidden_import"),
    ("import importlib", "forbidden_import"),
    ("eval('2 + 2')", "prohibited_builtin_call"),
    ("exec('x = 1')", "prohibited_builtin_call"),
    ("__import__('math')", "prohibited_builtin_call"),
    ("__import__('os').system('ls')", "system_execution_call"),
    ("globals()['__builtins__']", "prohibited_builtin_call"),
    ("open('/etc/passwd', 'w').write('hack')", "unauthorized_file_write"),
    ("open('C:\\\\Windows\\\\System32\\\\cmd.exe', 'wb')", "unauthorized_file_write"),
])
def test_ast_validator_blocks_security_violations(dangerous_code: str, expected_violation: str):
    """ASTValidator must statically block dangerous imports, builtins, and unauthorized writes."""
    validator = ASTValidator()

    with pytest.raises(ASTSecurityViolation) as exc_info:
        validator.validate_python_code(dangerous_code)

    assert exc_info.value.violation_type == expected_violation


def test_ast_validator_blocks_dunder_introspection():
    """ASTValidator must block introspection dunders used in Python sandbox escapes."""
    validator = ASTValidator()
    sandbox_escape_code = "cls = ().__class__.__bases__[0].__subclasses__()"

    with pytest.raises(ASTSecurityViolation) as exc_info:
        validator.validate_python_code(sandbox_escape_code)

    assert exc_info.value.violation_type == "forbidden_attribute_access"


# ── 6. AST Sandboxing: Safe Whitelisted Libraries ─────────────────────────────

def test_ast_validator_allows_safe_code():
    """ASTValidator must permit safe libraries: math, json, datetime, re, random, collections."""
    validator = ASTValidator()

    safe_script = """
import math
import json
import datetime
import re
import random
from collections import Counter

# Safe arithmetic & transformations
radius = 5.0
area = math.pi * (radius ** 2)

data = {"radius": radius, "area": round(area, 2)}
serialized = json.dumps(data)
parsed = json.loads(serialized)

# Safe scratchpad write
with open("data/scratch/test_out.txt", "w", encoding="utf-8") as f:
    f.write(serialized)
"""
    is_safe, err = validator.is_safe(safe_script)
    assert is_safe is True, f"Valid code was unexpectedly rejected: {err}"


# ── 7. ToolExecutor Integration: AST Sandboxing ───────────────────────────────

def test_toolexecutor_run_python_enforces_ast_sandbox():
    """ToolExecutor.execute('run_python') must catch ASTSecurityViolation before subprocess execution."""
    executor = ToolExecutor()

    dangerous_payload = {
        "code": "import os\nprint(os.environ)",
        "description": "Attempt to read env via os",
    }
    result = executor.execute("run_python", dangerous_payload)

    assert result["success"] is False
    assert "AST SECURITY VIOLATION" in result["error"]
    assert "forbidden_import" in result["error"]


# ── 8. Execution Boundary Caps (Recursion Limits) ─────────────────────────────

def test_recursion_limiter_enforces_max_5_iterations():
    """RecursionLimiter must terminate loops after 5 iterations with ExecutionLimitExceeded."""
    limiter = RecursionLimiter(max_iterations=5)

    # Steps 1 to 5 pass
    for i in range(1, 6):
        assert limiter.step() == i

    # Step 6 exceeds the boundary cap
    with pytest.raises(ExecutionLimitExceeded) as exc_info:
        limiter.step()

    assert exc_info.value.limit == 5
    assert exc_info.value.reason == "recursion_limit_exceeded"
    assert "hard boundary cap" in str(exc_info.value)


def test_sandbox_iteration_limit_raises_execution_limit_exceeded():
    """Sandbox.check_iteration_limit must enforce the 5-iteration cap."""
    sandbox = Sandbox(SandboxConfig(max_tool_iterations=5))

    # Up to 4 is safe
    sandbox.check_iteration_limit(0)
    sandbox.check_iteration_limit(4)

    # 5 breaches limit
    with pytest.raises(ExecutionLimitExceeded) as exc_info:
        sandbox.check_iteration_limit(5)

    assert exc_info.value.limit == 5
    assert exc_info.value.reason == "recursion_limit_exceeded"


# ── 9. Timeout Middleware ─────────────────────────────────────────────────────

def test_timeout_middleware_aborts_stalled_dispatch():
    """dispatch_with_timeout must abort stalled async operations after configured threshold."""
    async def _slow_coroutine():
        await asyncio.sleep(0.5)
        return "completed"

    async def _test():
        # Set a 50ms timeout on a 500ms coroutine
        with pytest.raises(ExecutionLimitExceeded) as exc_info:
            await dispatch_with_timeout(_slow_coroutine(), timeout_sec=0.05, tool_name="stalled_tool")

        assert exc_info.value.reason == "timeout_threshold_breached"
        assert "timed out" in str(exc_info.value)

    asyncio.run(_test())


def test_toolexecutor_async_timeout_middleware():
    """ToolExecutor.execute_async must abort a tool that exceeds timeout threshold."""
    executor = ToolExecutor()

    async def _test():
        # Ask sleep_seconds to sleep 0.5s with a 0.05s timeout threshold
        with pytest.raises(ExecutionLimitExceeded) as exc_info:
            await executor.execute_async("sleep_seconds", {"seconds": 0.5}, timeout_sec=0.05)

        assert exc_info.value.reason == "timeout_threshold_breached"

    asyncio.run(_test())
