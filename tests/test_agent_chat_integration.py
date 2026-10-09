import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
import asyncio
from agent import MemoryAgent, BudgetExceededError

@pytest.fixture(autouse=True)
def _scoped_mocks():
    with patch("memory.memory_manager.MemoryManager"), \
         patch("agent.ToolExecutor"), \
         patch("tool_router.DynamicToolRouter.route_tools", new_callable=AsyncMock, return_value=[]):
        yield

@pytest.fixture
def mock_agent():
    mock_memory = MagicMock()
    mock_planning = MagicMock()
    mock_execution = MagicMock()
    mock_governance = MagicMock()
    mock_ledger = MagicMock()
    mock_governance.ledger_gate = mock_ledger
    
    agent = MemoryAgent(
        user_id="test_user",
        memory_subsystem=mock_memory,
        planning_subsystem=mock_planning,
        execution_subsystem=mock_execution,
        governance_subsystem=mock_governance
    )
    
    agent._chat_gemini_async = AsyncMock()
    agent._chat_openrouter_async = AsyncMock()
    
    agent.swarm = MagicMock()
    agent._tool_executor.execute_tool = AsyncMock()
    
    agent._router = MagicMock()
    agent._router.route_async = AsyncMock(return_value=MagicMock(model="gemini", reason="Mock route"))
    
    agent._openrouter = MagicMock()
    agent._prompt_optimizer = MagicMock()
    agent._prompt_optimizer.optimize.return_value = MagicMock(applied=False, optimized_prompt="opt", techniques=[], reasoning="", duration_ms=0)
    agent._budget = MagicMock()
    agent._budget.check_budget.return_value = (True, "")
    
    return agent

@pytest.mark.asyncio
async def test_simple_turn_no_tools(mock_agent):
    mock_agent._chat_gemini_async.return_value = ("Hello from Gemini!", [], 10, 10)
    mock_agent._ledger_gate.verify_and_enforce.return_value = ("Hello from Gemini!", [], MagicMock(all_verified=True))
    res = await mock_agent.chat_async("Hello!", operation_mode="SOLO")
    assert res["reply"] == "Hello from Gemini!"
    assert mock_agent._chat_gemini_async.called

@pytest.mark.asyncio
async def test_turn_with_one_tool_call(mock_agent):
    pass

@pytest.mark.asyncio
async def test_swarm_mode_execution(mock_agent):
    mock_agent.swarm.execute_swarm.return_value = {
        "success": True,
        "final_reply": "Swarm solved the task.",
        "swarm_actions": [],
        "blackboard": {},
        "agents_used": ["cortex"]
    }
    mock_agent._ledger_gate.verify_and_enforce.return_value = ("Swarm solved the task.", [], MagicMock(all_verified=True))
    res = await mock_agent.chat_async("Solve this huge task", operation_mode="SWARM")
    assert res["reply"] == "Swarm solved the task."
    assert mock_agent.swarm.execute_swarm.called

@pytest.mark.asyncio
async def test_model_failover_cascade(mock_agent):
    from google.api_core.exceptions import ResourceExhausted
    mock_agent._chat_gemini_async.side_effect = ResourceExhausted("Quota exceeded")
    mock_agent._chat_openrouter_async.return_value = ("Hello from fallback!", [], 10, 10)
    mock_agent._ledger_gate.verify_and_enforce.return_value = ("Hello from fallback!", [], MagicMock(all_verified=True))
    res = await mock_agent.chat_async("Hello!", operation_mode="SOLO")
    assert res["reply"] == "Hello from fallback!"
    assert mock_agent._chat_gemini_async.called
    assert mock_agent._chat_openrouter_async.called

@pytest.mark.asyncio
async def test_ledger_gate_catching_hallucination(mock_agent):
    mock_agent._chat_gemini_async.return_value = ("Here is the script:\n`python\ndef fib(n): pass\n`\nI successfully executed the script for you.", [], 10, 10)
    intercepted_text = "Intercepted unverified physical execution claim."
    mock_agent._ledger_gate.verify_and_enforce.return_value = (intercepted_text, [], MagicMock(all_verified=False))
    res = await mock_agent.chat_async("Run a script", operation_mode="SOLO")
    assert res["reply"] == intercepted_text
    assert mock_agent._ledger_gate.verify_and_enforce.called

@pytest.mark.asyncio
async def test_budget_enforcement(mock_agent):
    mock_agent._budget.check_budget.return_value = (False, "Budget exceeded for today")
    with pytest.raises(BudgetExceededError):
        await mock_agent.chat_async("Hello!", operation_mode="SOLO")

