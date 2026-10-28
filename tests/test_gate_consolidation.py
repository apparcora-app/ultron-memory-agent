"""
tests/test_gate_consolidation.py — Unit tests for Phase 4:
Gate consolidation, single-pass synthesis, and latency/token multiplier optimization.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ultron.core.pipeline.context import PipelineContext
from ultron.core.pipeline.stages.execution_stage import ExecutionStage
from ultron.core.pipeline.stages.verification_stage import VerificationStage
from ultron.agent import MemoryAgent


@pytest.fixture
def mock_agent():
    mock_memory = MagicMock()
    mock_planning = MagicMock()
    mock_execution = MagicMock()
    mock_governance = MagicMock()
    mock_ledger = MagicMock()
    mock_governance.ledger_gate = mock_ledger

    with patch("memory.memory_manager.MemoryManager"), \
         patch("agent.ToolExecutor"), \
         patch("tool_router.DynamicToolRouter.route_tools", new_callable=AsyncMock, return_value=[]):
        agent = MemoryAgent(
            user_id="test_gate_user",
            memory_subsystem=mock_memory,
            planning_subsystem=mock_planning,
            execution_subsystem=mock_execution,
            governance_subsystem=mock_governance,
        )

    agent._chat_gemini_async = AsyncMock()
    agent._chat_openrouter_async = AsyncMock()
    agent._tool_executor = MagicMock()
    agent._tool_executor.execute.return_value = {
        "success": True,
        "output": "42",
        "error": None,
        "duration_ms": 15,
    }
    agent._critic = MagicMock()
    agent._ledger_gate = MagicMock()
    agent._call_raw_llm = MagicMock()

    return agent


@pytest.mark.asyncio
async def test_pre_synthesizer_code_execution(mock_agent):
    """Verify that Python code in worker reply is executed before Synthesizer pass."""
    worker_reply_with_code = "I will calculate this:\n```python\nprint(6 * 7)\n```"
    synth_reply = "The answer is 42."

    mock_agent._chat_gemini_async.side_effect = [
        (worker_reply_with_code, [{"tool": "dummy", "output": "ok"}], 10, 10),
        (synth_reply, [], 15, 15),
    ]

    stage = ExecutionStage()
    ctx = PipelineContext(
        agent=mock_agent,
        user_input="Calculate 6 * 7",
        operation_mode="SOLO",
    )
    ctx.effective_mode = "SOLO"
    ctx.tools_param = [{"name": "run_python"}]
    ctx.selected_model = "gemini-2.0-flash"

    await stage.execute(ctx)

    # Verify run_python was executed directly
    assert ctx.pre_synth_code_executed is True
    assert any(a["tool"] == "run_python" for a in ctx.tool_actions)
    assert ctx.synthesizer_critic_applied is True
    assert ctx.draft_reply == synth_reply


@pytest.mark.asyncio
async def test_critic_gate_bypass_when_consolidated(mock_agent):
    """Verify that In-Flight Critic re-prompt is bypassed when single-pass synthesis embedded directives."""
    stage = VerificationStage()
    ctx = PipelineContext(
        agent=mock_agent,
        user_input="Reconcile data",
        operation_mode="SOLO",
    )
    ctx.draft_reply = "Reconciliation complete: 0 variances found."
    ctx.tool_actions = [
        {"tool": "run_python", "output": "Variance: 0"},
        {"tool": "file_operation", "output": "File saved"},
    ]
    ctx.synthesizer_critic_applied = True
    ctx.route_reason = "Standard Tool Route"

    mock_agent._ledger_gate.verify_and_enforce.return_value = (
        ctx.draft_reply,
        ctx.tool_actions,
        MagicMock(all_verified=True, failed_intents=0),
    )

    await stage.execute(ctx)

    # Critic verify_in_flight should NOT be called because directives were applied in synthesis
    assert mock_agent._critic.verify_in_flight.called is False
    assert ctx.final_reply == "Reconciliation complete: 0 variances found."


@pytest.mark.asyncio
async def test_critic_gate_runs_when_complex_mode_flagged(mock_agent):
    """Verify that Critic still acts as safety net when route_reason flags COMPLEX."""
    stage = VerificationStage()
    ctx = PipelineContext(
        agent=mock_agent,
        user_input="Complex multi-system reconciliation",
        operation_mode="SOLO",
    )
    ctx.draft_reply = "Draft reply."
    ctx.tool_actions = [
        {"tool": "run_python", "output": "ok"},
        {"tool": "file_operation", "output": "ok"},
    ]
    ctx.synthesizer_critic_applied = True
    ctx.route_reason = "COMPLEX_ROUTING"

    mock_agent._ledger_gate.verify_and_enforce.return_value = (
        ctx.draft_reply,
        ctx.tool_actions,
        MagicMock(all_verified=True, failed_intents=0),
    )
    mock_agent._critic.verify_in_flight.return_value = MagicMock(
        approved=True,
        critique="",
        correction_instruction="",
    )

    await stage.execute(ctx)

    # In COMPLEX mode, Critic still runs as an extra assurance gate
    assert mock_agent._critic.verify_in_flight.called is True


@pytest.mark.asyncio
async def test_ledger_gate_always_enforces_physical_truth(mock_agent):
    """Verify that Ledger Gate always enforces physical ground truth even with consolidated Critic."""
    stage = VerificationStage()
    ctx = PipelineContext(
        agent=mock_agent,
        user_input="Create file report.csv",
        operation_mode="SOLO",
    )
    ctx.draft_reply = "I created report.csv successfully."
    ctx.tool_actions = []  # No actual file write occurred!
    ctx.synthesizer_critic_applied = True

    intercepted_msg = "VIOLATION: No physical file_operation was executed."
    mock_agent._ledger_gate.verify_and_enforce.return_value = (
        intercepted_msg,
        [],
        MagicMock(all_verified=False, failed_intents=1, remediation_instructions="Fix hallucination"),
    )
    mock_agent._call_raw_llm.return_value = "I apologize, the file was not created because the tool was not called."

    await stage.execute(ctx)

    assert mock_agent._ledger_gate.verify_and_enforce.called is True
    assert mock_agent._call_raw_llm.called is True
    assert "not created" in ctx.final_reply
