import time
import sys
import os

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from crewai import LLM, Agent, Task, Crew
from crewai.llm import crewai_event_bus, LLMCallStartedEvent, LLMCallCompletedEvent

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
    
    print("\n" + "=" * 80)
    print(f">> [LIVE LLM CALL #{log_entry['call_index']}] - AGENT: {log_entry['agent_role']} ({duration_ms}ms, ~{log_entry['total_tokens']} tokens)")
    print("-" * 80)
    print(">>> ACTUAL PROMPT SENT:")
    print(raw_prompt[:200] + "...")
    print("-" * 80)
    print("<<< ACTUAL RESPONSE RECEIVED:")
    print(raw_response[:200] + "...")
    print("=" * 80 + "\n")
    sys.stdout.flush()

crewai_event_bus.register_handler(LLMCallStartedEvent, on_llm_start)
crewai_event_bus.register_handler(LLMCallCompletedEvent, on_llm_complete)

llm = LLM(
    model="openai/gpt-oss-120b",
    base_url="http://localhost:31415/v1",
    api_key="sk-dummy-free-router-key-00000000000000000000000000000000000000000",
    temperature=0.0
)

a = Agent(role="TestAgent", goal="Respond with test", backstory="A tester", llm=llm, verbose=False)
t = Task(description="Respond with 'Test Passed'", expected_output="The string Test Passed", agent=a)
c = Crew(agents=[a], tasks=[t], verbose=False)
res = c.kickoff()
print("FINAL RES:", res)
print("TOTAL CALLS LOGGED:", len(call_logs))
