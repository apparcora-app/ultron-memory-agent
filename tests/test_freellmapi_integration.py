"""
tests/test_freellmapi_integration.py — FreeLLMAPI Gateway & Fallback Layer Tests.

Verifies:
1. ModelRegistry integration: ModelProvider.FREELLMAPI and candidate rotation pools.
2. LLMConfig settings for FreeLLMAPI.
3. MemoryAgent initialization with FreeLLMAPI client bridge.
4. Raw LLM tertiary fallback to FreeLLMAPI on primary provider outages.
5. 3-tier failover chain (Gemini -> OpenRouter -> FreeLLMAPI) via TieredModelFailover.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from config import LLMConfig
from governance.model_registry import (
    ModelRegistry,
    ModelProvider,
    DEFAULT_ROTATION_POOLS,
)
from resilience.failover import (
    ModelProviderCandidate,
    TieredModelFailover,
    create_default_failover_chain,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


from agent import MemoryAgent


# ── 1. ModelRegistry FreeLLMAPI Tests ─────────────────────────────────────────

def test_model_registry_freellmapi_pool():
    registry = ModelRegistry()
    assert ModelProvider.FREELLMAPI == "freellmapi"
    pool = registry.get_candidate_pool("freellmapi")
    assert len(pool) >= 5
    assert "auto" in pool
    assert "groq/llama-3.3-70b-versatile" in pool


def test_model_registry_freellmapi_preferred_model():
    registry = ModelRegistry()
    pool = registry.get_candidate_pool("freellmapi", preferred_model="custom/free-model")
    assert pool[0] == "custom/free-model"
    assert "auto" in pool


# ── 2. LLMConfig FreeLLMAPI Settings Tests ────────────────────────────────────

def test_llm_config_freellmapi_defaults(monkeypatch):
    monkeypatch.delenv("FREELLMAPI_BASE_URL", raising=False)
    monkeypatch.delenv("FREELLMAPI_API_KEY", raising=False)
    monkeypatch.delenv("FREELLMAPI_ENABLED", raising=False)
    monkeypatch.delenv("FREELLMAPI_MODEL", raising=False)

    cfg = LLMConfig()
    assert cfg.freellmapi_base_url in ("http://localhost:3001/v1", "http://localhost:31415/v1")
    assert cfg.freellmapi_api_key in ("sk-freellmapi-local", cfg.freellmapi_api_key)
    assert cfg.freellmapi_enabled is True
    assert cfg.freellmapi_model == "auto"


def test_llm_config_freellmapi_overrides(monkeypatch):
    monkeypatch.setenv("FREELLMAPI_BASE_URL", "http://192.168.1.100:8080/v1")
    monkeypatch.setenv("FREELLMAPI_API_KEY", "sk-custom-unified-token")
    monkeypatch.setenv("FREELLMAPI_ENABLED", "true")
    monkeypatch.setenv("FREELLMAPI_MODEL", "groq/llama-3.3-70b")

    cfg = LLMConfig()
    assert cfg.freellmapi_base_url == "http://192.168.1.100:8080/v1"
    assert cfg.freellmapi_api_key == "sk-custom-unified-token"
    assert cfg.freellmapi_enabled is True
    assert cfg.freellmapi_model == "groq/llama-3.3-70b"


# ── 3. MemoryAgent FreeLLMAPI Client Initialization ──────────────────────────

def test_memory_agent_freellmapi_client_init():
    cfg = LLMConfig(
        freellmapi_base_url="http://localhost:3001/v1",
        freellmapi_api_key="sk-test",
        freellmapi_enabled=True,
    )

    mock_memory = MagicMock()
    mock_planning = MagicMock()
    mock_execution = MagicMock()
    mock_governance = MagicMock()

    agent = MemoryAgent(
        user_id="test_freellmapi_agent",
        llm_cfg=cfg,
        memory_subsystem=mock_memory,
        planning_subsystem=mock_planning,
        execution_subsystem=mock_execution,
        governance_subsystem=mock_governance,
    )

    assert hasattr(agent, "_freellmapi")
    assert agent._freellmapi is not None
    assert str(agent._freellmapi.base_url) in ("http://localhost:3001/v1/", "http://localhost:31415/v1/")


# ── 4. Raw LLM Tertiary Fallback to FreeLLMAPI ────────────────────────────────

def test_call_raw_llm_falls_back_to_freellmapi():
    cfg = LLMConfig(
        freellmapi_base_url="http://localhost:3001/v1",
        freellmapi_api_key="sk-test",
        freellmapi_enabled=True,
    )

    agent = MemoryAgent(
        user_id="test_fallback_user",
        llm_cfg=cfg,
        memory_subsystem=MagicMock(),
        planning_subsystem=MagicMock(),
        execution_subsystem=MagicMock(),
        governance_subsystem=MagicMock(),
    )

    # Simulate Gemini outage / None client
    agent._gemini = None
    agent._openrouter = None

    # Mock FreeLLMAPI client chat response
    mock_choice = MagicMock()
    mock_choice.message.content = "Response from FreeLLMAPI aggregated pool."
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    agent._freellmapi = MagicMock()
    agent._freellmapi.chat.completions.create.return_value = mock_resp

    output = agent._call_raw_llm("Analyze corporate structure")
    assert output == "Response from FreeLLMAPI aggregated pool."
    assert agent._freellmapi.chat.completions.create.called


# ── 5. Three-Tier Failover (Gemini -> OpenRouter -> FreeLLMAPI) ───────────────

@pytest.mark.anyio
async def test_3tier_failover_gemini_to_freellmapi():
    async def failing_gemini(prompt, system=""):
        raise RuntimeError("Gemini HTTP 429 Too Many Requests")

    async def failing_openrouter(prompt, system=""):
        raise RuntimeError("OpenRouter HTTP 503 Service Unavailable")

    async def successful_freellmapi(prompt, system=""):
        return "FreeLLMAPI Groq Llama 3.3 output"

    failover_chain = create_default_failover_chain(
        gemini_caller=failing_gemini,
        openrouter_caller=failing_openrouter,
        freellmapi_caller=successful_freellmapi,
    )

    result = await failover_chain.execute("Calculate tax liability")
    assert result.failover_occurred is True
    assert result.provider_used == "freellmapi"
    assert result.output == "FreeLLMAPI Groq Llama 3.3 output"
    assert len(result.fallback_reasons) == 2
    assert "gemini" in result.fallback_reasons[0].lower()
    assert "openrouter" in result.fallback_reasons[1].lower()


# ── 6. Dedicated Routing & Slash Command Tests ─────────────────────────────────

@pytest.mark.anyio
async def test_route_model_freellmapi_override():
    agent = MemoryAgent(
        user_id="test_route_user",
        llm_cfg=LLMConfig(),
        memory_subsystem=MagicMock(),
        planning_subsystem=MagicMock(),
        execution_subsystem=MagicMock(),
        governance_subsystem=MagicMock(),
    )

    model, reason = await agent.select_model(
        user_input="Hello Ultron",
        model_override="freellmapi",
    )
    assert model == "freellmapi"
    assert "FreeLLMAPI" in reason

    model, reason = await agent.select_model(
        user_input="Hello Ultron",
        model_override="freellmapi/groq/llama-3.3-70b-versatile",
    )
    assert model == "freellmapi/groq/llama-3.3-70b-versatile"
    assert "FreeLLMAPI" in reason


@pytest.mark.anyio
async def test_route_model_slash_freellm_command():
    agent = MemoryAgent(
        user_id="test_route_user",
        llm_cfg=LLMConfig(),
        memory_subsystem=MagicMock(),
        planning_subsystem=MagicMock(),
        execution_subsystem=MagicMock(),
        governance_subsystem=MagicMock(),
    )

    model, reason = await agent.select_model(
        user_input="/freellm generate an executive summary",
    )
    assert model == "freellmapi"
    assert "Manual FreeLLMAPI Override" in reason


@pytest.mark.anyio
async def test_chat_openrouter_async_dispatches_to_freellmapi():
    agent = MemoryAgent(
        user_id="test_dispatch_user",
        llm_cfg=LLMConfig(freellmapi_model="auto"),
        memory_subsystem=MagicMock(),
        planning_subsystem=MagicMock(),
        execution_subsystem=MagicMock(),
        governance_subsystem=MagicMock(),
    )

    mock_choice = MagicMock()
    mock_choice.message.content = "Direct output from FreeLLMAPI Sovereign Node"
    mock_choice.message.model_dump.return_value = {"role": "assistant", "content": "Direct output from FreeLLMAPI Sovereign Node"}
    mock_choice.message.tool_calls = None
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_resp.usage.prompt_tokens = 15
    mock_resp.usage.completion_tokens = 25

    agent._freellmapi = MagicMock()
    agent._freellmapi.chat.completions.create.return_value = mock_resp

    reply, tools, in_tok, out_tok = await agent._chat_openrouter_async(
        selected_model="freellmapi",
        system_prompt="You are Ultron",
        user_input="Run sovereign diagnostic",
    )

    assert "Direct output from FreeLLMAPI Sovereign Node" in reply
    assert in_tok == 15
    assert out_tok == 25
    assert agent._freellmapi.chat.completions.create.called
    call_kwargs = agent._freellmapi.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == "auto"
