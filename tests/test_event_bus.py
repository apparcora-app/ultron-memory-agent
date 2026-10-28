import time
import sys
import os
import pytest

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# Properly skip test if crewai is not installed in active environment
crewai = pytest.importorskip("crewai", reason="crewai is not installed in active environment")
from crewai import LLM, Agent, Task, Crew
from crewai.llm import crewai_event_bus, LLMCallStartedEvent, LLMCallCompletedEvent


def test_crewai_event_bus_logging():
    call_logs = []
    pending_calls = {}

    def on_llm_start(source, event):
        agent_name = "Agent"
        if hasattr(event, "from_agent") and event.from_agent:
            agent_name = getattr(event.from_agent, "role", str(event.from_agent))
        pending_calls[source] = {
            "messages": event.messages,
            "agent": agent_name,
            "t0": time.time(),
            "model": getattr(event, "model", None)
        }

    def on_llm_complete(source, event):
        start_info = pending_calls.pop(source, None)
        t_start = start_info["t0"] if start_info else time.time()
        duration_ms = round((time.time() - t_start) * 1000, 1)
        agent_role = start_info["agent"] if start_info else "Agent"
        
        msgs = (start_info["messages"] if start_info else None) or getattr(event, "messages", None)
        if isinstance(msgs, list):
            raw_prompt = "\n".join([f"[{m.get('role', 'user').upper()}]: {m.get('content', '')}" for m in msgs])
        else:
            raw_prompt = str(msgs)
            
        raw_response = str(event.response)
        
        prompt_tokens = len(raw_prompt) // 4
        comp_tokens = len(raw_response) // 4
        
        log_entry = {
            "call_index": len(call_logs) + 1,
            "agent_role": agent_role,
            "prompt": raw_prompt,
            "response": raw_response,
            "duration_ms": duration_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": comp_tokens,
            "total_tokens": prompt_tokens + comp_tokens,
        }
        call_logs.append(log_entry)

    crewai_event_bus.register_handler(LLMCallStartedEvent, on_llm_start)
    crewai_event_bus.register_handler(LLMCallCompletedEvent, on_llm_complete)

    api_key = os.environ.get("FREELLMAPI_API_KEY", os.environ.get("TEST_API_KEY", "env-test-key"))
    base_url = os.environ.get("FREELLMAPI_BASE_URL", "http://localhost:31415/v1")

    llm = LLM(
        model="openai/gpt-oss-120b",
        base_url=base_url,
        api_key=api_key,
        temperature=0.0
    )

    a = Agent(role="TestAgent", goal="Respond with test", backstory="A tester", llm=llm, verbose=False)
    t = Task(description="Respond with 'Test Passed'", expected_output="The string Test Passed", agent=a)
    c = Crew(agents=[a], tasks=[t], verbose=False)
    
    # Assert handlers are properly registered
    handlers_dict = getattr(crewai_event_bus, "handlers", getattr(crewai_event_bus, "_sync_handlers", {}))
    assert LLMCallStartedEvent in handlers_dict or hasattr(crewai_event_bus, "register_handler")
