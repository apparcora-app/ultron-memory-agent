"""
tests/test_cognitive_pipeline.py — Unit test suite for Phase 3:
CognitivePipeline decomposition, stage execution, and lifecycle management.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ultron.core.pipeline.context import PipelineContext
from ultron.core.pipeline.dispatcher import CognitivePipeline
from ultron.core.pipeline.stages.context_stage import ContextStage
from ultron.core.pipeline.stages.execution_stage import ExecutionStage
from ultron.core.pipeline.stages.verification_stage import VerificationStage
from ultron.agent import MemoryAgent, BudgetExceededError


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
            user_id="test_pipeline_user",
            memory_subsystem=mock_memory,
            planning_subsystem=mock_planning,
            execution_subsystem=mock_execution,
            governance_subsystem=mock_governance,
        )

    agent._chat_gemini_async = AsyncMock(return_value=("Mock Gemini reply", [], 10, 10))
    agent._chat_openrouter_async = AsyncMock(return_value=("Mock OpenRouter reply", [], 10, 10))
    agent.swarm = MagicMock()
    agent._tool_executor.execute_tool = AsyncMock()
    agent._router = MagicMock()
    agent._router.route_async = AsyncMock(return_value=MagicMock(model="gemini", reason="Mock route"))
    agent._openrouter = MagicMock()
    agent._prompt_optimizer = MagicMock()
    agent._prompt_optimizer.optimize.return_value = MagicMock(
        applied=False, optimized_prompt="opt", techniques=[], reasoning="", duration_ms=0
    )
    agent._budget = MagicMock()
    agent._budget.check_budget.return_value = (True, "")

    return agent


@pytest.mark.asyncio
async def test_pipeline_context_initialization_and_termination(mock_agent):
    ctx = PipelineContext(
        agent=mock_agent,
        user_input="Hello world",
        operation_mode="SOLO",
    )
    assert ctx.is_terminated is False
    assert ctx.early_result is None

    ctx.terminate_early({"reply": "Fast response", "early": True})
    assert ctx.is_terminated is True
    assert ctx.early_result["early"] is True


@pytest.mark.asyncio
async def test_context_stage_budget_rejection(mock_agent):
    mock_agent._budget.check_budget.return_value = (False, "Exhausted token budget")
    stage = ContextStage()
    ctx = PipelineContext(agent=mock_agent, user_input="Hello")

    with pytest.raises(BudgetExceededError):
        await stage.execute(ctx)


@pytest.mark.asyncio
async def test_context_stage_fast_path(mock_agent):
    stage = ContextStage()
    ctx = PipelineContext(agent=mock_agent, user_input="Hello!")

    await stage.execute(ctx)
    assert ctx.is_terminated is True
    assert ctx.early_result is not None
    assert ctx.early_result.get("fast_path") is True
    assert "Mock Gemini reply" in ctx.early_result["reply"]


@pytest.mark.asyncio
async def test_execution_stage_swarm_delegation(mock_agent):
    mock_agent.swarm.execute_swarm.return_value = {
        "success": True,
        "final_reply": "Swarm executed successfully.",
        "swarm_actions": [{"agent": "cortex", "action": "delegate"}],
        "blackboard": {},
    }
    stage = ExecutionStage()
    ctx = PipelineContext(
        agent=mock_agent,
        user_input="Complex multi-agent directive",
        operation_mode="SWARM",
    )
    ctx.effective_mode = "SWARM"
    ctx.effective_input = "Complex multi-agent directive"

    await stage.execute(ctx)
    assert ctx.is_terminated is True
    assert ctx.early_result["is_swarm"] is True
    assert ctx.early_result["reply"] == "Swarm executed successfully."


@pytest.mark.asyncio
async def test_verification_stage_ledger_and_anti_slop(mock_agent):
    stage = VerificationStage()
    ctx = PipelineContext(agent=mock_agent, user_input="Perform data reconciliation")
    ctx.draft_reply = "Operational status: Optimal. All subroutines online. The findings are verified in Table 1."
    ctx.tool_actions = [{"tool": "run_python", "output": "Done"}]

    mock_agent._ledger_gate.verify_and_enforce.return_value = (
        ctx.draft_reply,
        ctx.tool_actions,
        MagicMock(all_verified=True, failed_intents=0),
    )

    await stage.execute(ctx)
    # Anti-slop sanitizer should strip robotic phrases
    assert "Operational status: Optimal" not in ctx.final_reply
    assert "All subroutines online" not in ctx.final_reply
    assert "The findings are verified in Table 1." in ctx.final_reply


@pytest.mark.asyncio
async def test_cognitive_pipeline_end_to_end_lifecycle(mock_agent):
    mock_agent._ledger_gate.verify_and_enforce.return_value = (
        "Final clean pipeline response.",
        [],
        MagicMock(all_verified=True, failed_intents=0),
    )

    res = await mock_agent.chat_async("Analyze database latency metrics", operation_mode="SOLO")
    assert res["reply"] == "Final clean pipeline response."

    # Test lifecycle drain and shutdown
    assert mock_agent.drain(timeout=2.0) is True
    mock_agent.shutdown(timeout=2.0)
    assert mock_agent._learning_supervisor.get_stats()["is_alive"] is False
